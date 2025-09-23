package main

import (
	"context" // Import context package for timeout
	"flag"
	"fmt"
	"net/http"
	"sync" // Import sync package for WaitGroup
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var apiTimeout = 10 * time.Second // Define a variable for API timeout, default to 10 seconds
var apiProbeInterval = 30 * time.Second // Default sleep duration

// Define the list of APIs to monitor
type API struct {
	Name string
	URL  string
}

// Custom flag type for multiple URLs
type apiURLs []string

func (i *apiURLs) String() string {
	return fmt.Sprint(*i)
}

func (i *apiURLs) Set(value string) error {
	*i = append(*i, value)
	return nil
}

var (
	targetAPIs []API

	// 1. Define Prometheus metrics
	// Use Gauge metric, 1 for success, 0 for failure
	apiStatusGauge = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "api_availability_status",
			Help: "API availability status (1 for up, 0 for down)",
		},
		[]string{"api_name"}, // Use labels to differentiate between different APIs
	)

	// Use Gauge to record API response time
	apiLatencyGauge = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "api_response_seconds",
			Help: "API response time in seconds",
		},
		[]string{"api_name"},
	)
)

// 2. Define the probe function
func probeAPI(api API) {
	fmt.Printf("Probing %s at %s...\n", api.Name, api.URL)
	start := time.Now()

	// Create a context with a timeout
	ctx, cancel := context.WithTimeout(context.Background(), apiTimeout)
	defer cancel() // Ensure the context is canceled to release resources

	// Create an HTTP client with the context
	req, err := http.NewRequestWithContext(ctx, "GET", api.URL, nil)
	if err != nil {
		fmt.Printf("  -> FAILED to create request, error: %v\n", err)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(0)
		apiLatencyGauge.With(prometheus.Labels{"api_name": api.Name}).Set(apiTimeout.Seconds()) // Set latency to timeout on request creation failure
		return
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	latency := time.Since(start).Seconds()

	if err != nil {
		fmt.Printf("  -> FAILED, error: %v\n", err)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(0)
		apiLatencyGauge.With(prometheus.Labels{"api_name": api.Name}).Set(apiTimeout.Seconds()) // Set latency to timeout on HTTP request failure
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		fmt.Printf("  -> SUCCESS, response time: %.2fs\n", latency)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(1)
	} else {
		fmt.Printf("  -> FAILED, status code: %d\n", resp.StatusCode)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(0)
	}

	// Record response time regardless of success or failure
	apiLatencyGauge.With(prometheus.Labels{"api_name": api.Name}).Set(latency)
}

// 3. Main program entry point
func main() {
	var urls apiURLs
	flag.Var(&urls, "url", "URL to monitor (can be specified multiple times)")
	flag.DurationVar(&apiTimeout, "timeout", apiTimeout, "Timeout for API probes (e.g., 5s, 1m). Defaults to 10s if not provided.")
	flag.DurationVar(&apiProbeInterval, "interval", apiProbeInterval, "Interval between API probes (e.g., 30s, 1m). Defaults to 30s if not provided.")
	flag.Parse()

	if len(urls) == 0 {
		fmt.Println("No URLs provided to monitor. Use -url flag (e.g., -url https://www.baidu.com -url https://another-api.com/health)")
		return
	}

	// Populate targetAPIs from the parsed URLs
	for i, u := range urls {
		targetAPIs = append(targetAPIs, API{Name: fmt.Sprintf("api_%d", i+1), URL: u})
	}

	// Register metrics
	prometheus.MustRegister(apiStatusGauge)
	prometheus.MustRegister(apiLatencyGauge)

	// Start a goroutine to periodically probe APIs
	go func() {
		for {
			var wg sync.WaitGroup
			for _, api := range targetAPIs {
				wg.Add(1)
				go probeSingleAPI(api, &wg)
			}
			wg.Wait() // Wait for all probes to complete

			// Wait for the specified sleep duration before the next probe
			fmt.Printf("Waiting for %v before the next probe...\n", apiProbeInterval)
			time.Sleep(apiProbeInterval)
		}
	}()

	// Start an HTTP server on port 8000 to expose metrics
	// This is the endpoint Prometheus will scrape
	http.Handle("/metrics", promhttp.Handler())
	fmt.Println("Prometheus metrics server started on http://localhost:8000")
	http.ListenAndServe(":8000", nil)
}

// probeSingleAPI is a helper function to probe a single API in a goroutine.
func probeSingleAPI(api API, wg *sync.WaitGroup) {
	defer wg.Done()
	probeAPI(api)
}
