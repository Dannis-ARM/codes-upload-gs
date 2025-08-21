import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.LoggerContext;
import org.slf4j.LoggerFactory;
import org.slf4j.Logger;

public class MyLoggerConfigurator {

    public static void main(String[] args) {
        // Step 1: 获取 Logback 的 LoggerContext
        LoggerContext loggerContext = (LoggerContext) LoggerFactory.getILoggerFactory();

        // Step 2: 获取指定的 logger 实例
        // 这里的 "com.example.myapp" 是你的包名或类名
        ch.qos.logback.classic.Logger logger = loggerContext.getLogger("com.example.myapp");

        // Step 3: 强制设置 logger 级别为 INFO
        logger.setLevel(Level.INFO);
        
        // 可选：设置根 logger 的级别
        // loggerContext.getLogger(Logger.ROOT_LOGGER_NAME).setLevel(Level.INFO);

        // 现在可以开始使用 SLF4J logger 了，它的级别已经被强制设置为 INFO
        Logger myAppLogger = LoggerFactory.getLogger(MyLoggerConfigurator.class);
        myAppLogger.info("这条日志会显示。");
        myAppLogger.debug("这条日志不会显示。");
        
        // 验证一下级别是否被正确设置
        System.out.println("Logger 'com.example.myapp' 的当前级别是: " + logger.getLevel());
    }
}