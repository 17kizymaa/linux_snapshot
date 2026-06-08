.PHONY: build test lint clean run install fmt

build:
	CGO_ENABLED=0 go build -ldflags="-s -w" -o ./bin/firetv ./cmd/firetv

test:
	go test -v ./...

lint:
	go vet ./...

clean:
	rm -rf ./bin/

run:
	go run ./cmd/firetv

install:
	go install ./cmd/firetv

fmt:
	go fmt ./...
