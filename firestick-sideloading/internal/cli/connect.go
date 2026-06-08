package cli

import (
	"fmt"

	"github.com/anphuni/firestick-sideloading/internal/errors"
	"github.com/spf13/cobra"
)

var (
	connectTimeout int
	connectForce   bool
)

func newConnectCmd(ds deviceServiceGetter) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "connect [IP|serial]",
		Short: "Connect to a Fire TV device",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			svc, err := ds(cmd)
			if err != nil {
				return err
			}
			target := args[0]
			fmt.Fprintf(cmd.OutOrStdout(), "Connecting to %s...\n", target)
			if err := svc.Connect(cmd.Context(), target); err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Connected to %s\n", target)
			return nil
		},
	}

	cmd.Flags().IntVar(&connectTimeout, "timeout", 30, "Connection timeout in seconds")
	cmd.Flags().BoolVar(&connectForce, "force", false, "Force reconnection")

	return cmd
}

func newDisconnectCmd(ds deviceServiceGetter) *cobra.Command {
	return &cobra.Command{
		Use:   "disconnect [IP|serial]",
		Short: "Disconnect from a Fire TV device",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			svc, err := ds(cmd)
			if err != nil {
				return err
			}
			target := args[0]
			if err := svc.Disconnect(cmd.Context(), target); err != nil {
				return err
			}
			fmt.Fprintf(cmd.OutOrStdout(), "Disconnected from %s\n", target)
			return nil
		},
	}
}

func getExitCode(err error) int {
	if ce, ok := err.(*errors.ClassifiedError); ok {
		return ce.ExitCode
	}
	return 1
}
