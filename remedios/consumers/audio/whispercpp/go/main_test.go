package main

import (
	"bytes"
	"context"
	"math"
	"os/exec"
	"testing"
)

// Test only the PCM decode path with an embedded 16kHz mono WAV.
func TestDecodeWavToPCM(t *testing.T) {
	if _, err := exec.LookPath("ffmpeg"); err != nil {
		t.Skip("ffmpeg not available, skipping")
	}

	// Minimal WAV header for 16-bit PCM, 16kHz mono, data size filled below.
	header := []byte{
		'R', 'I', 'F', 'F', 0, 0, 0, 0, 'W', 'A', 'V', 'E',
		'f', 'm', 't', ' ', 16, 0, 0, 0, 1, 0, 1, 0,
		0x80, 0x3E, 0, 0, // sample rate 16000
		0x00, 0x7D, 0, 0, // byte rate = sampleRate * numChannels * bitsPerSample/8
		2, 0, // block align
		16, 0, // bits per sample
		'd', 'a', 't', 'a', 0, 0, 0, 0,
	}

	// Generate 0.1s of a 440Hz sine in int16.
	var pcm bytes.Buffer
	samples := 1600 // 0.1s at 16kHz
	for i := 0; i < samples; i++ {
		sample := int16(30000 * math.Sin(2*math.Pi*440*float64(i)/16000))
		pcm.WriteByte(byte(sample))
		pcm.WriteByte(byte(sample >> 8))
	}

	data := pcm.Bytes()
	// Patch RIFF and data sizes.
	total := uint32(4 + (8 + 16) + (8 + len(data)))
	header[4], header[5], header[6], header[7] = byte(total), byte(total>>8), byte(total>>16), byte(total>>24)
	dataSize := uint32(len(data))
	header[40], header[41], header[42], header[43] = byte(dataSize), byte(dataSize>>8), byte(dataSize>>16), byte(dataSize>>24)

	wavBytes := append(header, data...)
	cfg := Config{FfmpegPath: "ffmpeg"}
	pcmOut, dur, err := convertToPCM(context.Background(), cfg, wavBytes)
	if err != nil {
		t.Fatalf("decodeWavToPCM failed: %v", err)
	}
	if len(pcmOut) != samples {
		t.Fatalf("unexpected samples: got %d want %d", len(pcmOut), samples)
	}
	if dur <= 0 {
		t.Fatalf("duration should be >0, got %f", dur)
	}
}
