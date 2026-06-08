package runtime

import (
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestForSerial(t *testing.T) {
	logger := zerolog.New(nil)
	runner := NewADBRunner(30*time.Second, logger)

	scoped := runner.ForSerial("192.168.1.50:5555")
	assert.NotNil(t, scoped)
	assert.Equal(t, "192.168.1.50:5555", scoped.serial)
	// Original should be unchanged
	assert.Equal(t, "", runner.serial)
}

func TestForSerial_PreservesTimeout(t *testing.T) {
	logger := zerolog.New(nil)
	runner := NewADBRunner(45*time.Second, logger)

	scoped := runner.ForSerial("ABCD1234")
	assert.Equal(t, 45*time.Second, scoped.timeout)
}
