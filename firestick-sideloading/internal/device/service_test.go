package device

import (
	"context"
	"testing"

	"github.com/anphuni/firestick-sideloading/pkg/proto"
	"github.com/stretchr/testify/assert"
)

// mockDeviceService is a test double for DeviceService.
type mockDeviceService struct {
	detectResult []proto.DeviceInfo
	detectErr    error
	connectErr   error
	infoResult   *proto.DeviceInfo
	infoErr      error
	healthErr    error
	disconnectErr error
}

func (m *mockDeviceService) Detect(ctx context.Context) ([]proto.DeviceInfo, error) {
	return m.detectResult, m.detectErr
}

func (m *mockDeviceService) Connect(ctx context.Context, target string) error {
	return m.connectErr
}

func (m *mockDeviceService) Info(ctx context.Context, serial string) (*proto.DeviceInfo, error) {
	return m.infoResult, m.infoErr
}

func (m *mockDeviceService) HealthCheck(ctx context.Context, serial string) error {
	return m.healthErr
}

func (m *mockDeviceService) Disconnect(ctx context.Context, target string) error {
	return m.disconnectErr
}

func (m *mockDeviceService) List(ctx context.Context) ([]proto.DeviceInfo, error) {
	return m.Detect(ctx)
}

func TestDeviceServiceInterface(t *testing.T) {
	// Verify mock satisfies the interface
	var _ DeviceService = &mockDeviceService{}
}

func TestDetectReturnsSlice(t *testing.T) {
	svc := &mockDeviceService{
		detectResult: []proto.DeviceInfo{
			{Serial: "192.168.1.50:5555", Model: "AFTMM", State: "device"},
		},
	}
	result, err := svc.Detect(context.Background())
	assert.NoError(t, err)
	assert.Len(t, result, 1)
	assert.Equal(t, "192.168.1.50:5555", result[0].Serial)
}

func TestHealthCheckReturnsError(t *testing.T) {
	svc := &mockDeviceService{
		healthErr: nil,
	}
	err := svc.HealthCheck(context.Background(), "serial")
	assert.NoError(t, err)

	svcErr := &mockDeviceService{
		healthErr: assert.AnError,
	}
	err = svcErr.HealthCheck(context.Background(), "serial")
	assert.Error(t, err)
}

func TestListDelegatesToDetect(t *testing.T) {
	svc := &mockDeviceService{
		detectResult: []proto.DeviceInfo{
			{Serial: "abc", Model: "AFTSSS", State: "device"},
		},
	}
	result, err := svc.List(context.Background())
	assert.NoError(t, err)
	assert.Len(t, result, 1)
	assert.Equal(t, "abc", result[0].Serial)
}
