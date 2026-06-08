package device

import (
	"context"

	"github.com/anphuni/firestick-sideloading/pkg/proto"
)

// DeviceService defines the device lifecycle operations.
type DeviceService interface {
	// Detect returns all connected ADB devices.
	Detect(ctx context.Context) ([]proto.DeviceInfo, error)

	// Connect establishes a network ADB connection to the target.
	Connect(ctx context.Context, target string) error

	// Info retrieves enriched device properties via getprop.
	Info(ctx context.Context, serial string) (*proto.DeviceInfo, error)

	// HealthCheck verifies the device is responsive via echo ping.
	HealthCheck(ctx context.Context, serial string) error

	// Disconnect cleanly disconnects from the target.
	Disconnect(ctx context.Context, target string) error

	// List is a convenience alias for Detect.
	List(ctx context.Context) ([]proto.DeviceInfo, error)
}
