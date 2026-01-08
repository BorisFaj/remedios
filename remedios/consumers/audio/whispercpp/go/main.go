package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"

	whisper "github.com/ggerganov/whisper.cpp/bindings/go/pkg/whisper"
	"github.com/segmentio/kafka-go"
)

type internalClient struct {
	baseURL string
	token   string
	client  *http.Client
}

var ffmpegArgs = []string{
	"-hide_banner", "-loglevel", "error",
	"-i", "pipe:0",
	"-ac", "1",
	"-ar", fmt.Sprint(whisper.SampleRate),
	"-acodec", "pcm_f32le",
	"-f", "f32le",
	"pipe:1",
}

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
	Bootstrap        string
	AudioTopic       string
	DLQTopic         string
	GroupID          string
	GraphURL         string
	GraphToken       string
	FfmpegPath       string
	ModelPath        string
	Language         string
	Threads          int
	InternalAPIURL   string
	InternalAPIToken string
}

type dlqProducer struct {
	writer *kafka.Writer
}

func newDLQProducer(cfg Config) *dlqProducer {
	return &dlqProducer{
		writer: &kafka.Writer{
			Addr:                   kafka.TCP(cfg.Bootstrap),
			Topic:                  cfg.DLQTopic,
			AllowAutoTopicCreation: true,
			BatchTimeout:           time.Second,
		},
	}
}

func (p *dlqProducer) Close() {
	if p == nil || p.writer == nil {
		return
	}
	_ = p.writer.Close()
}

func (p *dlqProducer) Send(ctx context.Context, m kafka.Message) error {
	if p == nil || p.writer == nil {
		return errors.New("dlq producer not initialized")
	}
	return p.writer.WriteMessages(ctx, m)
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

func newInternalClient(cfg Config) *internalClient {
	return &internalClient{
		baseURL: strings.TrimSuffix(cfg.InternalAPIURL, "/"),
		token:   cfg.InternalAPIToken,
		client:  &http.Client{Timeout: 10 * time.Second},
	}
}

func startHealthServer(port string) {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})

	addr := ":" + port
	go func() {
		if err := http.ListenAndServe(addr, mux); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Printf("health server error: %v", err)
		}
	}()
	log.Printf("health server on %s/health", addr)
}

func (c *internalClient) post(ctx context.Context, path string, payload any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode/100 != 2 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("internal api %s failed: status=%d body=%s", path, resp.StatusCode, string(respBody))
	}
	return nil
}

func loadConfig() Config {
	threads := runtime.NumCPU()
	if v := os.Getenv("WHISPER_THREADS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			threads = n
		}
	}
	return Config{
		Bootstrap:        mustEnv("BOOTSTRAP_SERVER", "", true),
		AudioTopic:       mustEnv("AUDIO_TOPIC", "transcription_requests", false),
		DLQTopic:         mustEnv("DLQ_TOPIC", "incoming.messages.text.dlq", false),
		GroupID:          mustEnv("GROUP_ID", "whatsapp-audio-consumer", false),
		GraphURL:         mustEnv("GRAPH_URL", "", true),
		GraphToken:       mustEnv("GRAPH_API_TOKEN", "", true),
		FfmpegPath:       mustEnv("FFMPEG_PATH", "ffmpeg", false),
		ModelPath:        mustEnv("WHISPER_MODEL", "/app/ggml-large-v3-turbo-q5_0.bin", false),
		Language:         os.Getenv("WHISPER_LANGUAGE"),
		Threads:          threads,
		InternalAPIURL:   mustEnv("INTERNAL_API_URL", "", true),
		InternalAPIToken: mustEnv("INTERNAL_API_TOKEN", "", true),
	}
}

func convertToPCM(ctx context.Context, cfg Config, audio []byte) ([]float32, float64, error) {
	if len(audio) == 0 {
		return nil, 0, errors.New("empty audio payload")
	}

	args := append([]string{cfg.FfmpegPath}, ffmpegArgs...)
	cmd := exec.CommandContext(ctx, args[0], args[1:]...)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	cmd.Stdin = bytes.NewReader(audio)

	if err := cmd.Run(); err != nil {
		return nil, 0, fmt.Errorf("ffmpeg failed: %w (%s)", err, stderr.String())
	}

	raw := stdout.Bytes()
	if len(raw) == 0 {
		return nil, 0, fmt.Errorf("ffmpeg produced empty pcm (stderr=%s)", stderr.String())
	}
	if len(raw)%4 != 0 {
		return nil, 0, fmt.Errorf("pcm output not aligned: %d bytes", len(raw))
	}

	samples := make([]float32, len(raw)/4)
	for i := 0; i < len(samples); i++ {
		bits := binary.LittleEndian.Uint32(raw[i*4:])
		samples[i] = math.Float32frombits(bits)
	}
	duration := float64(len(samples)) / float64(whisper.SampleRate)

	return samples, duration, nil
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
	body, err := io.ReadAll(resp2.Body)
	if err != nil {
		return nil, err
	}
	if len(body) == 0 {
		return nil, errors.New("downloaded empty audio payload")
	}
	return body, nil
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

func sendTextAnswer(ctx context.Context, cfg Config, msg AudioMessage, text string) error {
	if cfg.GraphURL == "" || cfg.GraphToken == "" {
		return errors.New("GRAPH_URL/GRAPH_API_TOKEN missing")
	}
	client := &http.Client{Timeout: 60 * time.Second}
	url := strings.TrimSuffix(cfg.GraphURL, "/") + "/" + msg.NumberID + "/messages"

	makeReq := func(body []byte) (*http.Request, error) {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Bearer "+cfg.GraphToken)
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")
		return req, nil
	}

	payload := map[string]any{
		"messaging_product": "whatsapp",
		"to":                fmt.Sprint(msg.Phone),
		"text":              map[string]string{"body": text},
		"context":           map[string]string{"message_id": msg.MessageID},
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	var lastErr error
	for attempt := 1; attempt <= 3; attempt++ {
		if attempt > 1 {
			time.Sleep(time.Duration(attempt) * time.Second)
		}
		req, err := makeReq(body)
		if err != nil {
			return err
		}
		resp, err := client.Do(req)
		if err != nil {
			lastErr = err
			log.Printf("send_text attempt=%d failed: %v", attempt, err)
			continue
		}
		func() {
			defer resp.Body.Close()
			if resp.StatusCode/100 != 2 {
				respBody, _ := io.ReadAll(resp.Body)
				lastErr = fmt.Errorf("send_text failed: status=%d body=%s", resp.StatusCode, string(respBody))
				log.Printf("send_text attempt=%d non-2xx: %v", attempt, lastErr)
				return
			}
			lastErr = nil
		}()
		if lastErr == nil {
			break
		}
	}
	if lastErr != nil {
		return lastErr
	}

	// Mark as read (best-effort)
	markPayload := map[string]any{
		"messaging_product": "whatsapp",
		"status":            "read",
		"message_id":        msg.MessageID,
	}
	markBody, err := json.Marshal(markPayload)
	if err != nil {
		log.Printf("mark_read marshal failed: %v", err)
		return nil
	}
	reqMark, err := makeReq(markBody)
	if err != nil {
		log.Printf("mark_read request build failed: %v", err)
		return nil
	}
	if resp, err := client.Do(reqMark); err != nil {
		log.Printf("mark_read failed: %v", err)
	} else {
		defer resp.Body.Close()
		if resp.StatusCode/100 != 2 {
			body, _ := io.ReadAll(resp.Body)
			log.Printf("mark_read non-2xx status=%d body=%s", resp.StatusCode, string(body))
		}
	}
	return nil
}

func handleMessage(ctx context.Context, cfg Config, internal *internalClient, mdl whisper.Model, value []byte) error {
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

	log.Printf("msg in job_id=%d audio_id=%s partition?=n/a", msg.JobID, msg.AudioID)
	startedAt := time.Now().UTC()
	if err := internal.post(ctx, "/internal/job_status", map[string]any{
		"job_id": msg.JobID,
		"status": "processing",
	}); err != nil {
		return fmt.Errorf("job_status processing: %w", err)
	}

	audioCtx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()

	audioBytes, err := fetchAudio(audioCtx, cfg, msg.AudioID)
	if err != nil {
		return err
	}
	log.Printf("downloaded audio job_id=%d bytes=%d", msg.JobID, len(audioBytes))
	pcm, duration, err := convertToPCM(audioCtx, cfg, audioBytes)
	if err != nil {
		return err
	}
	log.Printf("transcribing job_id=%d duration=%.2fs", msg.JobID, duration)
	text, err := transcribe(audioCtx, cfg, mdl, pcm)
	if err != nil {
		return err
	}
	finishedAt := time.Now().UTC()
	durationMs := finishedAt.Sub(startedAt).Milliseconds()

	if err := internal.post(ctx, "/internal/job_result", map[string]any{
		"job_id":                 msg.JobID,
		"result":                 map[string]any{"transcript": text, "audio_id": msg.AudioID},
		"output_ref":             "whisper-cpp",
		"duration_ms":            durationMs,
		"started_at":             startedAt.Format(time.RFC3339),
		"finished_at":            finishedAt.Format(time.RFC3339),
		"audio_duration_seconds": duration,
	}); err != nil {
		return fmt.Errorf("job_result: %w", err)
	}

	if err := internal.post(ctx, "/internal/job_status", map[string]any{
		"job_id": msg.JobID,
		"status": "completed",
	}); err != nil {
		return fmt.Errorf("job_status completed: %w", err)
	}
	if err := sendTextAnswer(audioCtx, cfg, msg, text); err != nil {
		return fmt.Errorf("send_text: %w", err)
	}

	log.Printf("job_id=%d ok text=%q duration=%.2fs", msg.JobID, text, duration)
	return nil
}

func main() {
	healthPort := os.Getenv("APP_PORT")
	if healthPort == "" {
		healthPort = "8001"
	}
	if os.Getenv("HEALTHCHECK_ONLY") == "1" {
		startHealthServer(healthPort)
		for {
			time.Sleep(60 * time.Second)
		}
	}

	startHealthServer(healthPort)
	cfg := loadConfig()
	internal := newInternalClient(cfg)
	dlq := newDLQProducer(cfg)
	defer dlq.Close()

	model, err := whisper.New(cfg.ModelPath)
	if err != nil {
		log.Fatalf("failed to load model: %v", err)
	}
	defer model.Close()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        []string{cfg.Bootstrap},
		Topic:          cfg.AudioTopic,
		GroupID:        cfg.GroupID,
		CommitInterval: 0, // manual commit after successful processing
	})
	defer reader.Close()

	log.Printf("consuming topic=%s group_id=%s", cfg.AudioTopic, cfg.GroupID)

	for {
		m, err := reader.FetchMessage(context.Background())
		if err != nil {
			log.Printf("read error: %v", err)
			time.Sleep(time.Second)
			continue
		}
		log.Printf("received message topic=%s partition=%d offset=%d", m.Topic, m.Partition, m.Offset)
		if err := handleMessage(context.Background(), cfg, internal, model, m.Value); err != nil {
			log.Printf("process error topic=%s partition=%d offset=%d: %v", m.Topic, m.Partition, m.Offset, err)
			payload, _ := json.Marshal(map[string]any{
				"error":     err.Error(),
				"raw":       string(m.Value),
				"topic":     m.Topic,
				"partition": m.Partition,
				"offset":    m.Offset,
			})
			if dlq != nil {
				if dlqErr := dlq.Send(context.Background(), kafka.Message{Value: payload}); dlqErr != nil {
					log.Printf("dlq send failed: %v", dlqErr)
				}
			}
			if err := reader.CommitMessages(context.Background(), m); err != nil {
				log.Printf("commit error after dlq topic=%s partition=%d offset=%d: %v", m.Topic, m.Partition, m.Offset, err)
			}
			continue
		}
		if err := reader.CommitMessages(context.Background(), m); err != nil {
			log.Printf("commit error topic=%s partition=%d offset=%d: %v", m.Topic, m.Partition, m.Offset, err)
		}
	}
}
