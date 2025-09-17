# Explanation of Functions in `main.go`

This document explains the purpose and usage of the key functions found in the `main.go` file, which is part of an API monitoring application.

## `(*apiURLs) String()`

**Purpose:** This method is part of the `apiURLs` custom type, which implements the `flag.Value` interface. It provides a string representation of the `apiURLs` slice.

**Usage:** When the `flag` package needs to display the current value of a flag of type `apiURLs` (e.g., for help messages or debugging), it calls this `String()` method to get a human-readable representation.

## `(*apiURLs) Set(value string) error`

**Purpose:** This method is also part of the `apiURLs` custom type and implements the `flag.Value` interface. It is responsible for parsing and setting a value provided via a command-line flag.

**Usage:** When a user specifies the `-url` flag on the command line (e.g., `-url https://example.com`), the `flag` package calls this `Set()` method with the provided URL string. The method appends the new URL to the `apiURLs` slice, allowing multiple URLs to be specified.

## `probeAPI(api API)`

**Purpose:** This function is responsible for actively checking the availability and response time of a single API endpoint.

**Usage:**
- It takes an `API` struct (containing `Name` and `URL`) as input.
- It initiates an HTTP GET request to the specified API URL with a defined timeout (`apiTimeout`).
- It measures the time taken for the API to respond.
- Based on the HTTP response status code and any network errors, it updates two Prometheus Gauge metrics:
    - `apiStatusGauge`: Set to `1` for success (HTTP 200 OK) or `0` for failure (any error or non-200 status).
    - `apiLatencyGauge`: Records the response time in seconds.
- It prints the probing status and response time to the console.

## `main()`

**Purpose:** This is the entry point of the Go application. It orchestrates the entire API monitoring process.

**Usage:**
- **Command-line Argument Parsing:** It parses command-line arguments, specifically looking for one or more `-url` flags to define the APIs to monitor.
- **Initialization:** If no URLs are provided, it prints a usage message and exits. Otherwise, it populates the `targetAPIs` slice with the provided URLs.
- **Prometheus Metrics Registration:** It registers the `apiStatusGauge` and `apiLatencyGauge` with the Prometheus default registry, making them available for scraping.
- **API Probing Goroutine:** It starts a new goroutine that continuously:
    - Iterates through all defined `targetAPIs`.
    - Calls `probeAPI()` for each API to check its status.
    - Pauses for 60 seconds before the next round of probing.
- **Prometheus Metrics Server:** It starts an HTTP server on `http://localhost:8000` that exposes the `/metrics` endpoint. This endpoint is where Prometheus will scrape the collected API metrics.
