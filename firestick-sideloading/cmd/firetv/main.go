package main

import (
	"os"

	"github.com/anphuni/firestick-sideloading/internal/cli"
)

func main() {
	if err := cli.Execute(); err != nil {
		os.Exit(getExitCode(err))
	}
}

func getExitCode(err error) int {
	type exitCoder interface {
		ExitCode() int
	}
	if ec, ok := err.(exitCoder); ok {
		return ec.ExitCode()
	}
	return 1
}
