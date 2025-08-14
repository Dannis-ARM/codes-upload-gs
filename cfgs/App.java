import com.fasterxml.jackson.databind.ObjectMapper;
import com.typesafe.config.Config;
import com.typesafe.config.ConfigFactory;
import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.util.Map;

public class App {
    public static void main(String[] args) {
        // Step 1: Load the YAML file
        InputStream inputStream = App.class.getClassLoader().getResourceAsStream("application.yaml");

        if (inputStream == null) {
            throw new IllegalArgumentException("YAML file not found on classpath!");
        }

        Yaml yaml = new Yaml();
        Map<String, Object> yamlMap = yaml.load(inputStream);

        // Step 2: Use Jackson's ObjectMapper to convert the Java Map to a JSON string
        ObjectMapper mapper = new ObjectMapper();
        String jsonString;
        try {
            jsonString = mapper.writeValueAsString(yamlMap);
        } catch (Exception e) {
            throw new RuntimeException("Error converting YAML map to JSON string", e);
        }
        
        // Step 3: Parse the JSON string with ConfigFactory
        Config config = ConfigFactory.parseString(jsonString);

        // Now you can use the Config object as before
        String dbHost = config.getString("database.host");
        int serverPort = config.getInt("server.port");
        String dbUser = config.getString("database.user");

        System.out.println("Database Host: " + dbHost);
        System.out.println("Server Port: " + serverPort);
        System.out.println("Database User: " + dbUser);
    }
}