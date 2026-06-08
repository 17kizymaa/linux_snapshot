package config

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/spf13/viper"
)

// AppConfig holds the parsed configuration values.
type AppConfig struct {
	ADBTimeout    time.Duration
	ADBServer     string
	ADBBind       string
	LogLevel      string
	DeviceDefault string
	ConfigDir     string
}

// InitConfig bootstraps Viper: config search paths, env prefix, defaults,
// and auto-creates ~/.config/firetv/config.yaml on first run.
func InitConfig() error {
	viper.SetConfigName("firetv")
	viper.SetConfigType("yaml")
	home, err := os.UserHomeDir()
	if err == nil {
		viper.AddConfigPath(filepath.Join(home, ".config", "firetv"))
	}
	viper.AddConfigPath(".")

	viper.SetEnvPrefix("FIRETV")
	viper.AutomaticEnv()

	viper.SetDefault("adb.timeout", "30s")
	viper.SetDefault("adb.server", "127.0.0.1:5037")
	viper.SetDefault("adb.bind", "127.0.0.1")
	viper.SetDefault("log.level", "info")
	viper.SetDefault("device.default", "")

	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); ok {
			home, herr := os.UserHomeDir()
			if herr != nil {
				return fmt.Errorf("cannot determine home directory: %w", herr)
			}
			configDir := filepath.Join(home, ".config", "firetv")
			if merr := os.MkdirAll(configDir, 0o755); merr != nil {
				return fmt.Errorf("create config dir: %w", merr)
			}
			configPath := filepath.Join(configDir, "config.yaml")
			defaults := []byte(
				"# Fire TV Sideloading Toolkit configuration\n" +
					"adb:\n" +
					"  timeout: 30s\n" +
					"  server: \"127.0.0.1:5037\"\n" +
					"  bind: \"127.0.0.1\"\n" +
					"log:\n" +
					"  level: info\n" +
					"device:\n" +
					"  default: \"\"\n",
			)
			if werr := os.WriteFile(configPath, defaults, 0o600); werr != nil {
				return fmt.Errorf("write default config: %w", werr)
			}
			// Re-read to populate viper
			viper.SetConfigFile(configPath)
			if rerr := viper.ReadInConfig(); rerr != nil {
				return fmt.Errorf("read default config: %w", rerr)
			}
		} else {
			return fmt.Errorf("read config: %w", err)
		}
	}

	return nil
}

// GetConfig reads current viper state into an AppConfig struct.
func GetConfig() (*AppConfig, error) {
	v := viper.GetViper()
	cfg := &AppConfig{
		ADBTimeout:    v.GetDuration("adb.timeout"),
		ADBServer:     v.GetString("adb.server"),
		ADBBind:       v.GetString("adb.bind"),
		LogLevel:      v.GetString("log.level"),
		DeviceDefault: v.GetString("device.default"),
		ConfigDir:     filepath.Dir(v.ConfigFileUsed()),
	}
	return cfg, nil
}
