package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"time"

	"github.com/segmentio/kafka-go"
	whisper "github.com/ggerganov/whisper.cpp/bindings/go/pkg/whisper"
	wav "github.com/go-audio/wav"
)

type IncomingMessage struct {
	SchemaVersion int       `json:"schema_version"`
	MessageID     string    `json:"message_id"`
	NumberID      string    `json:"number_id"`
	Phone         int       `json:"phone"`
	JobID         int       `json:"job_id"`
	MessageType   string    `json:"message_type"`
	Timestamp     time.Time `json:"timestamp"`
}

type AudioMessage struct {
	IncomingMessage
	AudioID         string `json:"audio_id"`
	MimeType        string `json:"mime_type"`
	DurationSeconds *int   `json:"duration_seconds"`
}

type Config struct {
	Bootstrap  string
	AudioTopic string
	DLQTopic   string
	GroupID    string
	GraphURL   string
	GraphToken string
	FfmpegPath string
	ModelPath  string
	Language   string
	Threads    int
}

func mustEnv(key, fallback string, required bool) string {
	val := os.Getenv(key)
	if val == "" {
		if required {
			log.Fatalf("missing required env %s", key)
		}
		return fallback
	}
	return val
}

func loadConfig() Config {
	threads := runtime.NumCPU()
	if v := os.Getenv("WHISPER_THREADS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			threads = n
		}
	}
	return Config{
		Bootstrap:  mustEnv("BOOTSTRAP_SERVER", "", true),
		AudioTopic: mustEnv("AUDIO_TOPIC", "transcription_requests", false),
		DLQTopic:   mustEnv("DLQ_TOPIC", "remedios_dlq", false),
		GroupID:    mustEnv("GROUP_ID", "whatsapp-audio-consumer", false),
		GraphURL:   mustEnv("GRAPH_URL", "", true),
		GraphToken: mustEnv("GRAPH_API_TOKEN", "", true),
		FfmpegPath: mustEnv("FFMPEG_PATH", "ffmpeg", false),
		ModelPath:  mustEnv("WHISPER_MODEL", "/app/ggml-large-v3-turbo-q5_0.bin", false),
		Language:   os.Getenv("WHISPER_LANGUAGE"),
		Threads:    threads,
	}
}

func convertToWav(ctx context.Context, cfg Config, audio []byte) ([]byte, error) {
	if len(audio) == 0 {
		return nil, errors.New("empty audio payload")
	}
	cmd := exec.CommandContext(ctx, cfg.FfmpegPath,
		"-i", "pipe:0",
		"-ac", "1",
		"-ar", fmt.Sprint(whisper.SampleRate),
		"-f", "wav",
		"pipe:1",
	)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	cmd.Stdin = bytes.NewReader(audio)
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("ffmpeg failed: %w (%s)", err, stderr.String())
	}
	wav := stdout.Bytes()
	if len(wav) == 0 {
		return nil, fmt.Errorf("ffmpeg produced empty wav (stderr=%s)", stderr.String())
	}
	return wav, nil
}

func decodeWavToPCM(wavBytes []byte) ([]float32, float64, error) {
	dec := wav.NewDecoder(bytes.NewReader(wavBytes))
	buf, err := dec.FullPCMBuffer()
	if err != nil {
		return nil, 0, err
	}
	if dec.SampleRate != whisper.SampleRate {
		return nil, 0, fmt.Errorf("unsupported sample rate: %d", dec.SampleRate)
	}
	if dec.NumChans != 1 {
		return nil, 0, fmt.Errorf("unsupported channels: %d", dec.NumChans)
	}
	data := buf.AsFloat32Buffer().Data
	if len(data) == 0 {
		return nil, 0, errors.New("empty PCM data after decode")
	}
	duration := float64(len(data)) / float64(dec.SampleRate)
	return data, duration, nil
}

func fetchAudio(ctx context.Context, cfg Config, audioID string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, fmt.Sprintf("%s/%s", cfg.GraphURL, audioID), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+cfg.GraphToken)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("meta lookup failed: %s", string(body))
	}

	var meta struct {
		URL string `json:"url"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&meta); err != nil {
		return nil, err
	}
	if meta.URL == "" {
		return nil, errors.New("empty media url")
	}

	req2, err := http.NewRequestWithContext(ctx, http.MethodGet, meta.URL, nil)
	if err != nil {
		return nil, err
	}
	req2.Header.Set("Authorization", "Bearer "+cfg.GraphToken)
	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		return nil, err
	}
	defer resp2.Body.Close()
	if resp2.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp2.Body)
		return nil, fmt.Errorf("audio download failed: %s", string(body))
	}
	return io.ReadAll(resp2.Body)
}

func transcribe(ctx context.Context, cfg Config, mdl whisper.Model, pcm []float32) (string, error) {
	context, err := mdl.NewContext()
	if err != nil {
		return "", err
	}
	if cfg.Language != "" {
		if err := context.SetLanguage(cfg.Language); err != nil {
			return "", err
		}
	}
	if cfg.Threads > 0 {
		context.SetThreads(uint(cfg.Threads))
	}
	if len(pcm) == 0 {
		return "", errors.New("cannot process empty PCM buffer")
	}

	if err := context.Process(pcm, nil, nil, nil); err != nil {
		return "", err
	}

	var text bytes.Buffer
	for {
		segment, err := context.NextSegment()
		if err == io.EOF {
			break
		} else if err != nil {
			return "", err
		}
		if segment.Text != "" {
			if text.Len() > 0 {
				text.WriteByte(' ')
			}
			text.WriteString(segment.Text)
		}
	}
	return text.String(), nil
}

func handleMessage(ctx context.Context, cfg Config, mdl whisper.Model, value []byte) error {
	var base IncomingMessage
	if err := json.Unmarshal(value, &base); err != nil {
		return fmt.Errorf("invalid json: %w", err)
	}
	if base.MessageType != "audio" {
		return fmt.Errorf("unsupported message_type=%s", base.MessageType)
	}
	var msg AudioMessage
	if err := json.Unmarshal(value, &msg); err != nil {
		return fmt.Errorf("invalid audio payload: %w", err)
	}

	audioCtx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()

	audioBytes, err := fetchAudio(audioCtx, cfg, msg.AudioID)
	if err != nil {
		return err
	}
	wavBytes, err := convertToWav(audioCtx, cfg, audioBytes)
	if err != nil {
		return err
	}
	pcm, duration, err := decodeWavToPCM(wavBytes)
	if err != nil {
		return err
	}
	text, err := transcribe(audioCtx, cfg, mdl, pcm)
	if err != nil {
		return err
	}
	log.Printf("job_id=%d ok text=%q duration=%.2fs", msg.JobID, text, duration)
	// TODO: update_job_status + save_job_result via DB/HTTP
	return nil
}

func main() {
	cfg := loadConfig()
	model, err := whisper.New(cfg.ModelPath)
	if err != nil {
		log.Fatalf("failed to load model: %v", err)
	}
	defer model.Close()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{cfg.Bootstrap},
		Topic:   cfg.AudioTopic,
		GroupID: cfg.GroupID,
	})
	defer reader.Close()

	log.Printf("consuming topic=%s group_id=%s", cfg.AudioTopic, cfg.GroupID)

	for {
		m, err := reader.ReadMessage(context.Background())
		if err != nil {
			log.Printf("read error: %v", err)
			time.Sleep(time.Second)
			continue
		}
		if err := handleMessage(context.Background(), cfg, model, m.Value); err != nil {
			log.Printf("process error topic=%s partition=%d offset=%d: %v", m.Topic, m.Partition, m.Offset, err)
			continue
		}
	}
}
