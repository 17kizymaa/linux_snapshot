package cli

import (
	"context"
	"fmt"
	"os"

	"github.com/anphuni/firestick-sideloading/internal/config"
	"github.com/anphuni/firestick-sideloading/internal/device"
	"github.com/anphuni/firestick-sideloading/internal/runtime"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	deviceFlag  string
	verboseFlag bool
	jsonFlag    bool
)

// deviceServiceGetter retrieves the DeviceService from the command context.
type deviceServiceGetter func(cmd *cobra.Command) (device.DeviceService, error)

// Execute runs the root command.
func Execute() error {
	return rootCmd.Execute()
}

var rootCmd = &cobra.Command{
	Use:   "firetv",
	Short: "Fire TV Stick sideloading toolkit",
	Long: `firetv — a single-command toolkit for Fire TV Stick sideloading on Arch Linux.
Detect devices, connect via network ADB, sideload APKs, mirror with scrcpy, and rollback.`,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		// Config init
		if err := config.InitConfig(); err != nil {
			return err
		}

		// Logging setup
		if verboseFlag {
			zerolog.SetGlobalLevel(zerolog.DebugLevel)
		} else {
			zerolog.SetGlobalLevel(zerolog.InfoLevel)
		}
		log.Logger = log.Output(zerolog.ConsoleWriter{
			Out:     os.Stderr,
			NoColor: false,
		})

		// ADB server lifecycle
		cfg, err := config.GetConfig()
		if err != nil {
			return err
		}
		runner := runtime.NewADBRunner(cfg.ADBTimeout, log.Logger)
		if err := runner.EnsureServer(cmd.Context()); err != nil {
			return err
		}

		// Inject DeviceService into command context
		svc := device.NewDeviceService(runner, log.Logger)
		cmd.SetContext(context.WithValue(cmd.Context(), deviceServiceKey{}, svc))

		return nil
	},
}

// deviceServiceKey is the context key for DeviceService.
type deviceServiceKey struct{}

// getDeviceService retrieves the DeviceService from the command context.
func getDeviceService(cmd *cobra.Command) (device.DeviceService, error) {
	val := cmd.Context().Value(deviceServiceKey{})
	if val == nil {
		return nil, fmt.Errorf("device service not initialized")
	}
	return val.(device.DeviceService), nil
}

func init() {
	rootCmd.PersistentFlags().StringVarP(&deviceFlag, "device", "d", "", "Target device serial or IP (overrides config)")
	rootCmd.PersistentFlags().BoolVarP(&verboseFlag, "verbose", "v", false, "Enable verbose output")
	rootCmd.PersistentFlags().BoolVar(&jsonFlag, "json", false, "Output JSON (Phase 4)")

	viper.BindPFlag("device.default", rootCmd.PersistentFlags().Lookup("device"))

	rootCmd.AddCommand(newDevicesCmd(getDeviceService))
	rootCmd.AddCommand(newDetectCmd(getDeviceService))
	rootCmd.AddCommand(newConnectCmd(getDeviceService))
	rootCmd.AddCommand(newStatusCmd(getDeviceService))
	rootCmd.AddCommand(setupCmd)
}
