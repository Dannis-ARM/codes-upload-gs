package main

import (
	"context" // Import context package for timeout
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"   // Import os package for log output
	"sync" // Import sync package for WaitGroup
	"time"

	"github.com/goccy/go-yaml"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var apiTimeout = 10 * time.Second       // Define a variable for API timeout, default to 10 seconds
var apiProbeInterval = 60 * time.Second // Default sleep duration

// Define the list of APIs to monitor
type API struct {
	Name string `yaml:"name,omitempty"` // Add yaml tags for unmarshaling
	URL  string `yaml:"url"`
}

// YAMLConfig defines the structure of the YAML configuration file
type YAMLConfig struct {
	MonitorAPIs []API `yaml:"monitor_apis"`
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

var (
	infoLogger  *log.Logger
	errorLogger *log.Logger
)

const (
	logLevelInfo  = "INFO"
	logLevelError = "ERROR"
)

// fmtLog formats the log message with ISO time and calls the appropriate logger.
func fmtLog(level string, format string, args ...interface{}) {
	timestamp := time.Now().Format(time.RFC3339) // ISO 8601 format
	message := fmt.Sprintf(format, args...)
	switch level {
	case logLevelInfo:
		infoLogger.Printf("%s - %s", timestamp, message)
	case logLevelError:
		errorLogger.Printf("%s - %s", timestamp, message)
	}
}

// 2. Define the probe function
func probeAPI(api API) {
	fmtLog(logLevelInfo, "Probing %s at %s...", api.Name, api.URL)
	start := time.Now()

	// Create a context with a timeout
	ctx, cancel := context.WithTimeout(context.Background(), apiTimeout)
	defer cancel() // Ensure the context is canceled to release resources

	// Create an HTTP client with the context
	req, err := http.NewRequestWithContext(ctx, "GET", api.URL, nil)
	if err != nil {
		fmtLog(logLevelError, "  -> FAILED to create request, error: %v", err)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(0)
		apiLatencyGauge.With(prometheus.Labels{"api_name": api.Name}).Set(apiTimeout.Seconds()) // Set latency to timeout on request creation failure
		return
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	latency := time.Since(start).Seconds()

	if err != nil {
		fmtLog(logLevelError, "  -> FAILED, error: %v", err)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(0)
		apiLatencyGauge.With(prometheus.Labels{"api_name": api.Name}).Set(apiTimeout.Seconds()) // Set latency to timeout on HTTP request failure
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		fmtLog(logLevelInfo, "  -> SUCCESS, response time: %.2fs", latency)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(1)
	} else {
		fmtLog(logLevelError, "  -> FAILED, status code: %d", resp.StatusCode)
		apiStatusGauge.With(prometheus.Labels{"api_name": api.Name}).Set(0)
	}

	// Record response time regardless of success or failure
	apiLatencyGauge.With(prometheus.Labels{"api_name": api.Name}).Set(latency)
}

// 3. Main program entry point
// loadYAMLConfig loads API configurations from a YAML file.
func loadYAMLConfig(filePath string) ([]API, error) {
	// Resolve file path: if it's just a filename, look in the current working directory
	if !isAbsolutePath(filePath) {
		cwd, err := os.Getwd()
		if err != nil {
			return nil, fmt.Errorf("failed to get current working directory: %w", err)
		}
		filePath = fmt.Sprintf("%s%c%s", cwd, os.PathSeparator, filePath)
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read YAML file %s: %w", filePath, err)
	}

	var config YAMLConfig
	err = yaml.Unmarshal(data, &config)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal YAML data from %s: %w", filePath, err)
	}

	// Assign default names if not provided in YAML
	for i := range config.MonitorAPIs {
		if config.MonitorAPIs[i].Name == "" {
			config.MonitorAPIs[i].Name = fmt.Sprintf("api_yaml_%d", i+1)
		}
	}

	return config.MonitorAPIs, nil
}

// isAbsolutePath checks if a given path is an absolute path.
func isAbsolutePath(path string) bool {
	return os.IsPathSeparator(path[0]) || (len(path) > 1 && path[1] == ':') // For Windows paths like C:\
}

// parseArgsAndLoadConfig handles CLI argument parsing and configuration loading.
func parseArgsAndLoadConfig() ([]API, time.Duration, time.Duration, error) {
	var urls apiURLs
	var yamlConfigPath string
	var timeout time.Duration
	var interval time.Duration

	flag.Var(&urls, "url", "URL to monitor (can be specified multiple times)")
	flag.StringVar(&yamlConfigPath, "yaml", "", "Path to a YAML configuration file for APIs")
	flag.DurationVar(&timeout, "timeout", apiTimeout, "Timeout for API probes (e.g., 5s, 1m). Defaults to 10s if not provided.")
	flag.DurationVar(&interval, "interval", apiProbeInterval, "Interval between API probes (e.g., 30s, 1m). Defaults to 30s if not provided.")
	flag.Parse()

	var apis []API
	if yamlConfigPath != "" {
		yamlAPIs, err := loadYAMLConfig(yamlConfigPath)
		if err != nil {
			return nil, 0, 0, fmt.Errorf("error loading YAML config: %w", err)
		}
		apis = append(apis, yamlAPIs...)
	} else {
		for i, u := range urls {
			apis = append(apis, API{Name: fmt.Sprintf("api_cmd_%d", i+1), URL: u})
		}
	}

	if len(apis) == 0 {
		return nil, 0, 0, fmt.Errorf("no URLs provided to monitor. Use -url flag or -yaml flag")
	}

	return apis, timeout, interval, nil
}

func main() {
	infoLogger = log.New(os.Stdout, "[INFO]  ", log.Lshortfile)
	errorLogger = log.New(os.Stdout, "[ERROR] ", log.Lshortfile)

	var err error
	targetAPIs, apiTimeout, apiProbeInterval, err = parseArgsAndLoadConfig()
	if err != nil {
		fmtLog(logLevelError, "%v", err)
		return
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
			fmtLog(logLevelInfo, "Waiting for %v before the next probe...", apiProbeInterval)
			time.Sleep(apiProbeInterval)
		}
	}()

	// Start an HTTP server on port 8000 to expose metrics
	// This is the endpoint Prometheus will scrape
	http.Handle("/metrics", promhttp.Handler())
	fmtLog(logLevelInfo, "Prometheus metrics server started on http://localhost:8000")
	http.ListenAndServe(":8000", nil)
}

// probeSingleAPI is a helper function to probe a single API in a goroutine.
func probeSingleAPI(api API, wg *sync.WaitGroup) {
	defer wg.Done()
	probeAPI(api)
}
