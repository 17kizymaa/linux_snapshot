package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

func newStatusCmd(ds deviceServiceGetter) *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Show current device connection health",
		RunE: func(cmd *cobra.Command, args []string) error {
			svc, err := ds(cmd)
			if err != nil {
				return err
			}
			devices, err := svc.List(cmd.Context())
			if err != nil {
				return err
			}
			if len(devices) == 0 {
				fmt.Fprintln(cmd.OutOrStdout(), "No devices connected.")
				fmt.Fprintln(cmd.OutOrStdout(), "Run: firetv connect <IP>")
				return nil
			}
			for _, d := range devices {
				fmt.Fprintf(cmd.OutOrStdout(), "Device: %s (%s)\n", d.Serial, d.Model)
				fmt.Fprintf(cmd.OutOrStdout(), "State:  %s\n", d.State)
				if err := svc.HealthCheck(cmd.Context(), d.Serial); err != nil {
					fmt.Fprintf(cmd.OutOrStdout(), "Health: UNHEALTHY — %s\n", err)
				} else {
					fmt.Fprintln(cmd.OutOrStdout(), "Health: OK")
				}
			}
			return nil
		},
	}
}
