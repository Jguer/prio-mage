.PHONY: build run shell clean help

# Default target
help:
	@echo "Available commands:"
	@echo "  build       - Build the Docker image"
	@echo "  run         - Run the container interactively"
	@echo "  shell       - Open a shell in the container"
	@echo "  clean       - Remove the Docker image"
	@echo "  list-issues - Run list-issues command"
	@echo "  update      - Run update-priorities with dry-run"
	@echo "  help        - Show this help message"

# Build the Docker image
build:
	docker build -t prio-mage .

# Run the container with docker-compose
run:
	docker-compose up

# Open a shell in the container
shell:
	docker run -it --rm --env-file .env prio-mage /bin/bash

# Run specific commands
list-issues:
	docker run --rm --env-file .env prio-mage list-issues --show-fields

update:
	docker run --rm --env-file .env prio-mage update-priorities --dry-run

project-info:
	docker run --rm --env-file .env prio-mage show-project-info

# Clean up
clean:
	docker rmi prio-mage || true
	docker-compose down --rmi all || true 