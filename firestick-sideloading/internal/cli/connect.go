package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

var (
	connectTimeout int
	connectForce   bool
)

var connectCmd = &cobra.Command{
	Use:   "connect [IP|serial]",
	Short: "Connect to a Fire TV device",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Fprintln(cmd.OutOrStdout(), "Connect not yet implemented.")
		fmt.Fprintf(cmd.OutOrStdout(), "Expected: connect to %s (timeout=%d, force=%v)\n", args[0], connectTimeout, connectForce)
		return nil
	},
}

func init() {
	connectCmd.Flags().IntVar(&connectTimeout, "timeout", 30, "Connection timeout in seconds")
	connectCmd.Flags().BoolVar(&connectForce, "force", false, "Force reconnection")
}
