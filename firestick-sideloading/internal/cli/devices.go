package cli

import (
	"fmt"

	"github.com/anphuni/firestick-sideloading/pkg/proto"
	"github.com/spf13/cobra"
)

func newDevicesCmd(ds deviceServiceGetter) *cobra.Command {
	return &cobra.Command{
		Use:   "devices",
		Short: "List all detected Fire TV devices",
		RunE: func(cmd *cobra.Command, args []string) error {
			svc, err := ds(cmd)
			if err != nil {
				return err
			}
			devices, err := svc.Detect(cmd.Context())
			if err != nil {
				return err
			}
			if len(devices) == 0 {
				fmt.Fprintln(cmd.OutOrStdout(), "No devices detected.")
				return nil
			}
			for _, d := range devices {
				fmt.Fprintf(cmd.OutOrStdout(), "%-20s %-15s %-12s %s\n", d.Serial, d.Model, d.State, connType(d))
			}
			return nil
		},
	}
}

func connType(d proto.DeviceInfo) string {
	if d.ConnectionType != "" {
		return d.ConnectionType
	}
	return "unknown"
}
