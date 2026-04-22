---
title: "Java设计模式（十六）：外观模式实战解析"
date: 2026-04-22T10:20:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "外观模式", "facade", "封装", "子系统"]
---

## 前言

外观模式（Facade Pattern）是一种结构型设计模式，它的核心思想是：**为子系统中的一组接口提供一个一致的界面（Facade），使得子系统更加容易使用**。

**核心思想**：封装复杂性，提供简化的高层接口。

<!--more-->

## 一、为什么需要外观模式

### 1.1 子系统复杂性

假设我们正在开发一个智能家居系统，有灯光、空调、音响、窗帘等多个子系统：

```java
// 不用外观模式：客户端需要了解所有子系统的细节
public class Client {
    public void watchMovie() {
        Light light = new Light();
        light.dim(20);
        
        AirConditioner ac = new AirConditioner();
        ac.setTemperature(24);
        ac.setMode("cooling");
        ac.setFanSpeed("medium");
        ac.turnOn();
        
        SoundSystem sound = new SoundSystem();
        sound.setVolume(30);
        sound.setSurround(true);
        sound.setInput("HDMI");
        sound.turnOn();
        
        Projector projector = new Projector();
        projector.setInput("HDMI");
        projector.setMode("cinema");
        projector.turnOn();
        
        Curtain curtain = new Curtain();
        curtain.close();
    }
}
```

客户端需要了解每个子系统的初始化细节和调用顺序，耦合度极高。外观模式将这些复杂性封装在一个简单的接口后面。

### 1.2 迪米特法则

外观模式符合迪米特法则（Law of Demeter）：一个对象应该对其他对象有尽可能少的了解。客户端只需要与外观对象交互，不需要了解子系统内部结构。

## 二、外观模式的结构

### 2.1 类图

```
┌───────────┐      ┌──────────────┐
│  Client   │─────>│   Facade     │
└───────────┘      │──────────────│
                   │ +operation() │
                   └──────┬───────┘
                          │
          ┌───────┬───────┼───────┬───────┐
          │       │       │       │       │
     ┌────┴──┐ ┌──┴───┐ ┌┴────┐ ┌┴─────┐ ┌┴──────┐
     │Sub A  │ │Sub B │ │Sub C│ │Sub D │ │Sub E  │
     └───────┘ └──────┘ └─────┘ └──────┘ └───────┘
```

### 2.2 核心角色

| 角色 | 职责 |
|------|------|
| Facade（外观） | 提供简化的高层接口，委托子系统完成工作 |
| Subsystem（子系统） | 实现具体功能，不知道 Facade 的存在 |
| Client（客户端） | 通过 Facade 与子系统交互 |

### 2.3 关键特点

外观模式没有抽象层，不像其他模式那样有复杂的继承体系。它的核心就是**封装和委托**：

- Facade 知道哪些子系统负责处理哪些请求
- 子系统不知道 Facade 的存在
- 客户端只与 Facade 交互

### 2.4 完整实现

```java
// ========== 1. 子系统：灯光 ==========
public class Light {
    public void turnOn() {
        System.out.println("💡 灯光已开启");
    }
    
    public void turnOff() {
        System.out.println("💡 灯光已关闭");
    }
    
    public void dim(int level) {
        System.out.println("💡 灯光调暗至 " + level + "%");
    }
}

// ========== 2. 子系统：空调 ==========
public class AirConditioner {
    private int temperature = 26;
    private String mode = "auto";
    
    public void turnOn() {
        System.out.println("❄️ 空调已开启");
    }
    
    public void turnOff() {
        System.out.println("❄️ 空调已关闭");
    }
    
    public void setTemperature(int temp) {
        this.temperature = temp;
        System.out.println("❄️ 空调温度设为 " + temp + "°C");
    }
    
    public void setMode(String mode) {
        this.mode = mode;
        System.out.println("❄️ 空调模式设为 " + mode);
    }
}

// ========== 3. 子系统：音响 ==========
public class SoundSystem {
    private int volume = 20;
    
    public void turnOn() {
        System.out.println("🔊 音响已开启");
    }
    
    public void turnOff() {
        System.out.println("🔊 音响已关闭");
    }
    
    public void setVolume(int vol) {
        this.volume = vol;
        System.out.println("🔊 音量设为 " + vol);
    }
    
    public void setSurround(boolean enable) {
        System.out.println("🔊 环绕声 " + (enable ? "开启" : "关闭"));
    }
}

// ========== 4. 子系统：投影仪 ==========
public class Projector {
    public void turnOn() {
        System.out.println("📽️ 投影仪已开启");
    }
    
    public void turnOff() {
        System.out.println("📽️ 投影仪已关闭");
    }
    
    public void setInput(String input) {
        System.out.println("📽️ 输入源设为 " + input);
    }
    
    public void setMode(String mode) {
        System.out.println("📽️ 显示模式设为 " + mode);
    }
}

// ========== 5. 子系统：窗帘 ==========
public class Curtain {
    public void open() {
        System.out.println("🪟 窗帘已打开");
    }
    
    public void close() {
        System.out.println("🪟 窗帘已关闭");
    }
}

// ========== 6. 外观：智能家居控制 ==========
public class SmartHomeFacade {
    private final Light light;
    private final AirConditioner ac;
    private final SoundSystem sound;
    private final Projector projector;
    private final Curtain curtain;
    
    public SmartHomeFacade() {
        this.light = new Light();
        this.ac = new AirConditioner();
        this.sound = new SoundSystem();
        this.projector = new Projector();
        this.curtain = new Curtain();
    }
    
    // 场景1：看电影
    public void watchMovie() {
        System.out.println("🎬 准备看电影...");
        curtain.close();
        light.dim(10);
        ac.setTemperature(24);
        ac.setMode("cooling");
        ac.turnOn();
        projector.setInput("HDMI");
        projector.setMode("cinema");
        projector.turnOn();
        sound.setSurround(true);
        sound.setVolume(30);
        sound.turnOn();
        System.out.println("🎬 电影模式就绪！");
    }
    
    // 场景2：结束电影
    public void endMovie() {
        System.out.println("🎬 结束电影...");
        sound.turnOff();
        projector.turnOff();
        light.turnOn();
        curtain.open();
        System.out.println("🎬 已退出电影模式");
    }
    
    // 场景3：阅读模式
    public void readingMode() {
        System.out.println("📖 进入阅读模式...");
        curtain.open();
        light.turnOn();
        ac.setTemperature(25);
        ac.setMode("auto");
        ac.turnOn();
        sound.turnOff();
        System.out.println("📖 阅读模式就绪！");
    }
    
    // 场景4：睡眠模式
    public void sleepMode() {
        System.out.println("😴 进入睡眠模式...");
        light.turnOff();
        curtain.close();
        sound.turnOff();
        projector.turnOff();
        ac.setTemperature(26);
        ac.setMode("sleep");
        ac.turnOn();
        System.out.println("😴 睡眠模式就绪！");
    }
}

// ========== 7. 客户端 ==========
public class SmartHomeDemo {
    public static void main(String[] args) {
        SmartHomeFacade smartHome = new SmartHomeFacade();
        
        // 简单的接口调用，无需了解子系统细节
        smartHome.watchMovie();
        System.out.println();
        smartHome.endMovie();
        System.out.println();
        smartHome.readingMode();
        System.out.println();
        smartHome.sleepMode();
    }
}
```

运行结果：

```
🎬 准备看电影...
🪟 窗帘已关闭
💡 灯光调暗至 10%
❄️ 空调温度设为 24°C
❄️ 空调模式设为 cooling
❄️ 空调已开启
📽️ 输入源设为 HDMI
📽️ 显示模式设为 cinema
📽️ 投影仪已开启
🔊 环绕声 开启
🔊 音量设为 30
🔊 音响已开启
🎬 电影模式就绪！

🎬 结束电影...
🔊 音响已关闭
📽️ 投影仪已关闭
💡 灯光已开启
🪟 窗帘已打开
🎬 已退出电影模式

📖 进入阅读模式...
🪟 窗帘已打开
💡 灯光已开启
❄️ 空调温度设为 25°C
❄️ 空调模式设为 auto
❄️ 空调已开启
🔊 音响已关闭
📖 阅读模式就绪！

😴 进入睡眠模式...
💡 灯光已关闭
🪟 窗帘已关闭
🔊 音响已关闭
📽️ 投影仪已关闭
❄️ 空调温度设为 26°C
❄️ 空调模式设为 sleep
❄️ 空调已开启
😴 睡眠模式就绪！
```

## 三、外观模式的高级用法

### 3.1 分层外观

对于特别复杂的系统，可以创建多层外观：

```java
// 底层外观：娱乐系统
public class EntertainmentFacade {
    private final SoundSystem sound;
    private final Projector projector;
    
    public void startEntertainment() {
        projector.setInput("HDMI");
        projector.turnOn();
        sound.setSurround(true);
        sound.turnOn();
    }
    
    public void stopEntertainment() {
        sound.turnOff();
        projector.turnOff();
    }
}

// 底层外观：环境系统
public class EnvironmentFacade {
    private final Light light;
    private final AirConditioner ac;
    private final Curtain curtain;
    
    public void setCinemaEnvironment() {
        curtain.close();
        light.dim(10);
        ac.setTemperature(24);
        ac.turnOn();
    }
    
    public void setNormalEnvironment() {
        curtain.open();
        light.turnOn();
    }
}

// 高层外观：组合底层外观
public class SmartHomeMasterFacade {
    private final EntertainmentFacade entertainment;
    private final EnvironmentFacade environment;
    
    public void watchMovie() {
        environment.setCinemaEnvironment();
        entertainment.startEntertainment();
    }
    
    public void endMovie() {
        entertainment.stopEntertainment();
        environment.setNormalEnvironment();
    }
}
```

### 3.2 外观与枚举场景

```java
public class SmartHomeEnumFacade {
    public enum Scene {
        MOVIE, READING, SLEEP, PARTY
    }
    
    private final Light light = new Light();
    private final AirConditioner ac = new AirConditioner();
    private final SoundSystem sound = new SoundSystem();
    
    public void applyScene(Scene scene) {
        switch (scene) {
            case MOVIE:
                light.dim(10);
                ac.setTemperature(24);
                ac.turnOn();
                sound.setVolume(30);
                sound.turnOn();
                break;
            case READING:
                light.turnOn();
                ac.setTemperature(25);
                ac.turnOn();
                break;
            case SLEEP:
                light.turnOff();
                ac.setMode("sleep");
                ac.turnOn();
                break;
            case PARTY:
                light.dim(50);
                ac.setTemperature(22);
                ac.turnOn();
                sound.setVolume(60);
                sound.turnOn();
                break;
        }
    }
}
```

### 3.3 外观模式与建造者模式结合

为复杂的外观操作提供流式接口：

```java
public class SmartHomeBuilderFacade {
    private final Light light = new Light();
    private final AirConditioner ac = new AirConditioner();
    private final SoundSystem sound = new SoundSystem();
    
    public SceneBuilder createScene() {
        return new SceneBuilder();
    }
    
    public class SceneBuilder {
        private int lightLevel = -1;
        private int temperature = -1;
        private int volume = -1;
        
        public SceneBuilder withLight(int level) {
            this.lightLevel = level;
            return this;
        }
        
        public SceneBuilder withTemperature(int temp) {
            this.temperature = temp;
            return this;
        }
        
        public SceneBuilder withSound(int vol) {
            this.volume = vol;
            return this;
        }
        
        public void apply() {
            if (lightLevel >= 0) {
                if (lightLevel == 0) light.turnOff();
                else light.dim(lightLevel);
            }
            if (temperature > 0) {
                ac.setTemperature(temperature);
                ac.turnOn();
            }
            if (volume >= 0) {
                sound.setVolume(volume);
                sound.turnOn();
            }
        }
    }
}

// 使用
SmartHomeBuilderFacade facade = new SmartHomeBuilderFacade();
facade.createScene()
    .withLight(20)
    .withTemperature(24)
    .withSound(40)
    .apply();
```

## 四、外观模式在 JDK 中的应用

### 4.1 java.util.Collections

`Collections` 类是外观模式的经典应用，它为一组集合操作提供了统一的接口：

```java
// Collections 是外观类，内部委托给各种算法实现
public class Collections {
    // 排序
    public static <T extends Comparable<? super T>> void sort(List<T> list) {
        list.sort(null);  // 委托给 List.sort()
    }
    
    // 二分查找
    public static <T> int binarySearch(List<? extends T> list, T key, Comparator<? super T> c) {
        // 委托给迭代器或随机访问实现
    }
    
    // 反转
    public static void reverse(List<?> list) { ... }
    
    // 打乱
    public static void shuffle(List<?> list) { ... }
    
    // 不可变集合
    public static <T> List<T> unmodifiableList(List<? extends T> list) { ... }
    
    // 同步包装
    public static <T> List<T> synchronizedList(List<T> list) { ... }
}
```

### 4.2 java.nio.file.Files

`Files` 类是 NIO 子系统的外观：

```java
// Files 为文件系统操作提供简化的接口
// 内部委托给 FileSystemProvider 等底层实现

// 读取所有行
List<String> lines = Files.readAllLines(Paths.get("data.txt"));

// 写入
Files.writeString(Paths.get("output.txt"), "Hello World");

// 复制
Files.copy(source, target);

// 遍历
try (Stream<Path> paths = Files.walk(Paths.get("/project"))) {
    paths.filter(p -> p.toString().endsWith(".java"))
         .forEach(System.out::println);
}
```

### 4.3 javax.sql.DataSource

JDBC 的 `DataSource` 是数据库连接子系统的外观：

```java
// DataSource 隐藏了驱动加载、连接创建等复杂性
DataSource ds = new HikariDataSource(config);
Connection conn = ds.getConnection();  // 简化！
```

### 4.4 java.util.logging.Logger

`Logger` 是日志子系统的外观：

```java
// Logger 隐藏了 Handler、Formatter、Level 等子系统的复杂性
Logger logger = Logger.getLogger("com.example");
logger.info("简单的一行代码");
// 内部：选择 Handler → 格式化 → 输出
```

## 五、外观模式 vs 其他模式

### 5.1 对比中介者模式

| 维度 | 外观模式 | 中介者模式 |
|------|---------|-----------|
| 方向 | 单向（客户端→外观→子系统） | 双向（同事→中介者→同事） |
| 目的 | 简化接口 | 解耦同事间交互 |
| 子系统 | 不知道外观存在 | 知道中介者存在 |
| 交互 | 客户端只调用外观 | 同事通过中介者通信 |

### 5.2 对比适配器模式

| 维度 | 外观模式 | 适配器模式 |
|------|---------|-----------|
| 目的 | 简化接口 | 转换接口 |
| 接口 | 提供新的简化接口 | 适配已有接口 |
| 子系统 | 多个子系统 | 通常一个 |
| 设计 | 正向设计 | 事后补救 |

### 5.3 对比建造者模式

| 维度 | 外观模式 | 建造者模式 |
|------|---------|-----------|
| 目的 | 简化调用 | 分步构建复杂对象 |
| 关注点 | 接口简化 | 对象创建 |
| 返回值 | 通常 void | 构建的产品 |

## 六、外观模式的优缺点

### 优点

1. **简化接口**：客户端无需了解子系统复杂性
2. **解耦**：客户端与子系统松耦合
3. **分层**：有助于建立分层架构
4. **不影响子系统**：子系统可以独立使用

### 缺点

1. **可能成为上帝对象**：外观承担过多职责
2. **不能替代子系统**：只是简化，不能替代直接使用
3. **新增子系统需修改外观**：违背开闭原则

### 适用场景

- 需要为复杂子系统提供简单接口
- 客户端与子系统之间存在很多依赖
- 需要构建分层架构
- 遗留系统的简化封装

## 七、实战：应用部署流程

用外观模式封装复杂的应用部署流程：

```java
// ========== 子系统 ==========
public class GitService {
    public void pull(String branch) {
        System.out.println("📥 拉取代码: " + branch);
    }
    
    public String getCommitHash() {
        String hash = "abc1234";
        System.out.println("📥 当前提交: " + hash);
        return hash;
    }
}

public class BuildService {
    public void compile() {
        System.out.println("🔨 编译项目...");
    }
    
    public void runTests() {
        System.out.println("🧪 运行测试...");
    }
    
    public void packageArtifact() {
        System.out.println("📦 打包产物...");
    }
}

public class DockerService {
    public void buildImage(String tag) {
        System.out.println("🐳 构建 Docker 镜像: " + tag);
    }
    
    public void pushImage(String tag) {
        System.out.println("🐳 推送镜像: " + tag);
    }
}

public class DeployService {
    public void deploy(String env, String imageTag) {
        System.out.println("🚀 部署到 " + env + "，镜像: " + imageTag);
    }
    
    public void healthCheck(String env) {
        System.out.println("❤️ 健康检查: " + env);
    }
}

public class NotifyService {
    public void notify(String message) {
        System.out.println("📢 通知: " + message);
    }
}

// ========== 外观 ==========
public class DeployFacade {
    private final GitService git = new GitService();
    private final BuildService build = new BuildService();
    private final DockerService docker = new DockerService();
    private final DeployService deploy = new DeployService();
    private final NotifyService notify = new NotifyService();
    
    // 完整部署流程
    public void fullDeploy(String branch, String env) {
        System.out.println("=== 开始部署流程 ===");
        
        try {
            // 1. 拉取代码
            git.pull(branch);
            String commitHash = git.getCommitHash();
            
            // 2. 构建测试
            build.compile();
            build.runTests();
            build.packageArtifact();
            
            // 3. Docker 镜像
            String imageTag = "app:" + commitHash;
            docker.buildImage(imageTag);
            docker.pushImage(imageTag);
            
            // 4. 部署
            deploy.deploy(env, imageTag);
            deploy.healthCheck(env);
            
            // 5. 通知
            notify.notify("✅ 部署成功！分支=" + branch + " 环境=" + env + " 提交=" + commitHash);
            
        } catch (Exception e) {
            notify.notify("❌ 部署失败: " + e.getMessage());
            throw e;
        }
        
        System.out.println("=== 部署完成 ===");
    }
    
    // 快速部署（跳过测试）
    public void quickDeploy(String branch, String env) {
        System.out.println("=== 快速部署 ===");
        git.pull(branch);
        String commitHash = git.getCommitHash();
        build.compile();
        build.packageArtifact();
        String imageTag = "app:" + commitHash;
        docker.buildImage(imageTag);
        docker.pushImage(imageTag);
        deploy.deploy(env, imageTag);
        notify.notify("⚡ 快速部署完成: " + commitHash);
    }
    
    // 回滚
    public void rollback(String env, String previousTag) {
        System.out.println("=== 回滚部署 ===");
        deploy.deploy(env, previousTag);
        deploy.healthCheck(env);
        notify.notify("🔄 已回滚到: " + previousTag);
    }
}

// ========== 客户端 ==========
public class DeployDemo {
    public static void main(String[] args) {
        DeployFacade deployer = new DeployFacade();
        
        // 一行代码完成完整部署
        deployer.fullDeploy("main", "production");
    }
}
```

运行结果：

```
=== 开始部署流程 ===
📥 拉取代码: main
📥 当前提交: abc1234
🔨 编译项目...
🧪 运行测试...
📦 打包产物...
🐳 构建 Docker 镜像: app:abc1234
🐳 推送镜像: app:abc1234
🚀 部署到 production，镜像: app:abc1234
❤️ 健康检查: production
📢 通知: ✅ 部署成功！分支=main 环境=production 提交=abc1234
=== 部署完成 ===
```

## 八、外观模式在 Spring 中的应用

### 8.1 JdbcTemplate

Spring 的 `JdbcTemplate` 是 JDBC 子系统的外观：

```java
// JdbcTemplate 隐藏了 Connection、Statement、ResultSet 的复杂性
@Repository
public class UserRepository {
    @Autowired
    private JdbcTemplate jdbcTemplate;
    
    // 一行代码完成查询，无需手动管理连接
    public User findById(Long id) {
        return jdbcTemplate.queryForObject(
            "SELECT * FROM users WHERE id = ?",
            (rs, rowNum) -> new User(rs.getLong("id"), rs.getString("name")),
            id
        );
    }
}
```

### 8.2 RestTemplate / RestClient

Spring 的 HTTP 客户端也是外观模式：

```java
// RestTemplate 隐藏了 HttpURLConnection / HttpClient 的复杂性
RestTemplate restTemplate = new RestTemplate();
String result = restTemplate.getForObject("https://api.example.com/data", String.class);
```

### 8.3 SpringApplication

Spring Boot 的 `SpringApplication` 是 Spring 生态的外观：

```java
@SpringBootApplication
public class MyApp {
    public static void main(String[] args) {
        // 一行代码启动整个 Spring 应用
        SpringApplication.run(MyApp.class, args);
    }
}
// 内部：创建 ApplicationContext → 注册 Bean → 自动配置 → 启动内嵌服务器
```

## 九、外观模式与函数式编程

### 9.1 使用函数式接口组合操作

```java
public class FunctionalFacade {
    private final List<Runnable> operations = new ArrayList<>();
    
    public FunctionalFacade light(Runnable action) {
        operations.add(action);
        return this;
    }
    
    public FunctionalFacade ac(Runnable action) {
        operations.add(action);
        return this;
    }
    
    public FunctionalFacade sound(Runnable action) {
        operations.add(action);
        return this;
    }
    
    public void execute() {
        operations.forEach(Runnable::run);
        operations.clear();
    }
}

// 使用
new FunctionalFacade()
    .light(() -> light.dim(20))
    .ac(() -> { ac.setTemperature(24); ac.turnOn(); })
    .sound(() -> { sound.setVolume(30); sound.turnOn(); })
    .execute();
```

### 9.2 使用 Consumer 链

```java
public class SceneConfigurer {
    public static void configure(Consumer<SceneBuilder> configurer) {
        SceneBuilder builder = new SceneBuilder();
        configurer.accept(builder);
        builder.apply();
    }
    
    public static class SceneBuilder {
        private int lightLevel = 100;
        private int temperature = 25;
        private int volume = 0;
        
        public SceneBuilder light(int level) { this.lightLevel = level; return this; }
        public SceneBuilder temp(int t) { this.temperature = t; return this; }
        public SceneBuilder volume(int v) { this.volume = v; return this; }
        
        public void apply() {
            System.out.println("应用场景: 灯光=" + lightLevel + "% 温度=" + temperature + "°C 音量=" + volume);
        }
    }
}

// 使用
SceneConfigurer.configure(scene -> scene.light(20).temp(24).volume(30));
```

## 十、面试常见问题

### Q1: 外观模式的核心思想是什么？

外观模式为复杂子系统提供一个简化的高层接口，使得子系统更容易使用。它不是封装子系统，而是提供一个更方便的入口。客户端可以选择使用外观，也可以直接使用子系统。

### Q2: 外观模式和适配器模式有什么区别？

适配器模式的目的是**转换接口**，让不兼容的接口能够协同工作；外观模式的目的是**简化接口**，让复杂的子系统更容易使用。适配器通常针对一个接口，外观通常针对多个子系统。

### Q3: 外观模式是否违反开闭原则？

严格来说，新增子系统时需要修改外观类，确实违反开闭原则。但外观模式的目的是简化，如果需要扩展，可以创建新的外观类，或使用分层外观来解决。

### Q4: 外观模式可以替代子系统吗？

不能。外观模式只是提供了一个更方便的入口，它不限制客户端直接使用子系统。在需要细粒度控制时，客户端仍然可以直接使用子系统。

### Q5: 什么场景下应该使用外观模式？

- 为复杂子系统提供简单接口
- 客户端与多个子系统耦合
- 构建分层架构
- 封装遗留系统

### Q6: 外观模式与中介者模式的区别？

外观是单向的——客户端调用外观，外观调用子系统，子系统不知道外观存在。中介者是双向的——同事对象通过中介者通信，同事知道中介者存在。外观简化接口，中介者解耦交互。

## 十一、总结

外观模式是最实用的设计模式之一，它不引入复杂的继承体系，只是简单地将复杂性封装在一个高层接口后面。

**核心要点**：

1. **简化接口**：一个方法代替多步操作
2. **解耦客户端**：客户端无需了解子系统细节
3. **迪米特法则**：减少客户端与子系统的直接交互
4. **JDK 应用**：Collections、Files、JdbcTemplate 都是经典实现
5. **不替代子系统**：外观是便利入口，不是唯一入口

外观模式告诉我们：**好的 API 设计不在于功能多强大，而在于能否让使用者轻松上手**。封装复杂性，暴露简单性——这就是外观模式的精髓。

---

**相关设计模式系列**：
- [Java设计模式（一）：单例模式完全指南](/posts/java设计模式一-单例模式完全指南/)
- [Java设计模式（二）：工厂模式深入详解](/posts/java设计模式二-工厂模式深入详解/)
- [Java设计模式（三）：建造者模式深度实践](/posts/java设计模式三-建造者模式深度实践/)
- [Java设计模式（四）：原型模式与对象克隆](/posts/java设计模式四-原型模式与对象克隆/)
- [Java设计模式（五）：适配器模式实战解析](/posts/java设计模式五-适配器模式实战解析/)
- [Java设计模式（六）：装饰器模式深入实践](/posts/java设计模式六-装饰器模式深入实践/)
- [Java设计模式（七）：观察者模式完全解析](/posts/java设计模式七-观察者模式完全解析/)
- [Java设计模式（八）：策略模式深度实践](/posts/java设计模式八-策略模式深度实践/)
- [Java设计模式（九）：模板方法模式完全指南](/posts/java设计模式九-模板方法模式完全指南/)
- [Java设计模式（十）：责任链模式深度实践](/posts/java设计模式十-责任链模式深度实践/)
- [Java设计模式（十一）：命令模式完全解析](/posts/java设计模式十一-命令模式完全解析/)
- [Java设计模式（十二）：迭代器模式深度实践](/posts/java设计模式十二-迭代器模式深度实践/)
- [Java设计模式（十三）：访问者模式深度实践](/posts/java设计模式十三-访问者模式深度实践/)
- [Java设计模式（十四）：组合模式深度实践](/posts/java设计模式十四-组合模式深度实践/)
- [Java设计模式（十五）：享元模式深度实践](/posts/java设计模式十五-享元模式深度实践/)
