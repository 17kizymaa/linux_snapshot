package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

func newDetectCmd(ds deviceServiceGetter) *cobra.Command {
	return &cobra.Command{
		Use:   "detect",
		Short: "Quick scan for connected Fire TV devices",
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
				fmt.Fprintln(cmd.OutOrStdout(), "No Fire TV devices detected. Ensure ADB is enabled on your device.")
				return nil
			}
			for _, d := range devices {
				fmt.Fprintf(cmd.OutOrStdout(), "Serial:          %s\n", d.Serial)
				fmt.Fprintf(cmd.OutOrStdout(), "Model:           %s\n", d.Model)
				fmt.Fprintf(cmd.OutOrStdout(), "State:           %s\n", d.State)
				fmt.Fprintf(cmd.OutOrStdout(), "Connection:      %s\n", d.ConnectionType)
				fmt.Fprintf(cmd.OutOrStdout(), "Fire OS:         %s\n", d.FireOSVersion)
				fmt.Fprintf(cmd.OutOrStdout(), "SDK Level:       %s\n", d.SDKLevel)
				fmt.Fprintf(cmd.OutOrStdout(), "Manufacturer:    %s\n", d.Manufacturer)
				fmt.Fprintln(cmd.OutOrStdout())
			}
			return nil
		},
	}
}
