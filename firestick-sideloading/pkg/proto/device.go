package proto

// DeviceInfo holds information about a detected Fire TV device.
type DeviceInfo struct {
	Serial         string `json:"serial"`
	Model          string `json:"model"`
	State          string `json:"state"`
	ConnectionType string `json:"connection_type"`
	FireOSVersion  string `json:"fire_os_version"`
	SDKLevel       string `json:"sdk_level"`
	Manufacturer   string `json:"manufacturer"`
}

// ConnectionState represents how a device is connected.
type ConnectionState string

const (
	ConnectionUSB     ConnectionState = "usb"
	ConnectionNetwork ConnectionState = "network"
	ConnectionUnknown ConnectionState = "unknown"
)

// DeviceFilter provides criteria for filtering device listings.
type DeviceFilter struct {
	BySerial    string
	ByState     string
	OnlyFireTV  bool
}
