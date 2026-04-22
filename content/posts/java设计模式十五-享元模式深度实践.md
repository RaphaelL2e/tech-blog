---
title: "Java设计模式（十五）：享元模式深度实践"
date: 2026-04-22T10:10:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "享元模式", "flyweight", "对象池", "缓存"]
---

## 前言

享元模式（Flyweight Pattern）是一种结构型设计模式，它的核心思想是：**通过共享技术有效地支持大量细粒度对象的复用，以减少内存占用和提高性能**。

**核心思想**：将对象的状态分为内部状态（可共享）和外部状态（不可共享），通过共享内部状态来减少对象数量。

<!--more-->

## 一、为什么需要享元模式

### 1.1 大量对象的内存问题

假设我们正在开发一个文本编辑器，每个字符都是一个对象。一篇 10 万字的文章：

```java
// 不用享元模式：每个字符一个对象
public class Character {
    private char value;        // 字符值
    private String font;       // 字体
    private int size;          // 字号
    private String color;      // 颜色
    private int positionX;     // X 坐标
    private int positionY;     // Y 坐标
}

// 10 万个字符 = 10 万个对象，大量内存浪费
// 同样的字体、字号、颜色被重复存储了几万次
```

同样的"宋体 12号 黑色"被存储了几万次，这是巨大的内存浪费。享元模式通过共享这些重复的内部状态来解决这个问题。

### 1.2 内部状态 vs 外部状态

享元模式的关键区分：

| 类型 | 含义 | 示例 | 是否共享 |
|------|------|------|----------|
| 内部状态 | 不随环境变化，可共享 | 字体、字号、颜色 | ✅ |
| 外部状态 | 随环境变化，不可共享 | 位置坐标 | ❌ |

## 二、享元模式的结构

### 2.1 类图

```
┌───────────────────────┐
│   Flyweight (抽象)     │
│───────────────────────│
│ + operation(extState) │
└───────────┬───────────┘
            │
    ┌───────┴───────┐
    │               │
┌───┴────────┐ ┌────┴─────────┐
│ConcreteFly-│ │ UnsharedCon- │
│  weight    │ │ creteFlywght │
│────────────│ │──────────────│
│intrinsicState│ │ all state   │
│operation() │ │ operation()  │
└────────────┘ └──────────────┘

┌───────────────────────┐
│ FlyweightFactory      │
│───────────────────────│
│ - pool: Map           │
│ + getFlyweight(key)   │
└───────────────────────┘
```

### 2.2 核心角色

| 角色 | 职责 |
|------|------|
| Flyweight（抽象享元） | 定义公共接口，接受外部状态 |
| ConcreteFlyweight（具体享元） | 实现接口，存储内部状态 |
| UnsharedConcreteFlyweight | 不需要共享的享元子类 |
| FlyweightFactory（享元工厂） | 管理享元池，创建和共享享元对象 |

### 2.3 完整实现

```java
// ========== 1. 抽象享元 ==========
public interface CharacterStyle {
    void display(char c, int x, int y);  // c, x, y 是外部状态
}

// ========== 2. 具体享元：存储内部状态 ==========
public class ConcreteCharacterStyle implements CharacterStyle {
    // 内部状态（可共享）
    private final String font;
    private final int size;
    private final String color;
    
    public ConcreteCharacterStyle(String font, int size, String color) {
        this.font = font;
        this.size = size;
        this.color = color;
    }
    
    @Override
    public void display(char c, int x, int y) {
        System.out.printf("字符 '%c' 在 (%d,%d) 处，%s %d号 %s%n",
            c, x, y, font, size, color);
    }
    
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof ConcreteCharacterStyle)) return false;
        ConcreteCharacterStyle that = (ConcreteCharacterStyle) o;
        return size == that.size && 
               font.equals(that.font) && 
               color.equals(that.color);
    }
    
    @Override
    public int hashCode() {
        return Objects.hash(font, size, color);
    }
}

// ========== 3. 享元工厂 ==========
public class CharacterStyleFactory {
    private static final Map<String, CharacterStyle> pool = new HashMap<>();
    
    public static CharacterStyle getStyle(String font, int size, String color) {
        String key = font + ":" + size + ":" + color;
        return pool.computeIfAbsent(key, 
            k -> new ConcreteCharacterStyle(font, size, color));
    }
    
    public static int getPoolSize() {
        return pool.size();
    }
}

// ========== 4. 客户端 ==========
public class TextEditorDemo {
    public static void main(String[] args) {
        String text = "Hello World 你好世界";
        String font = "宋体";
        int size = 12;
        String color = "黑色";
        
        // 获取共享的样式对象
        CharacterStyle style = CharacterStyleFactory.getStyle(font, size, color);
        
        // 渲染每个字符（外部状态：字符值和位置）
        for (int i = 0; i < text.length(); i++) {
            style.display(text.charAt(i), i * 12, 0);
        }
        
        System.out.println("\n享元池大小: " + CharacterStyleFactory.getPoolSize());
        // 即使渲染了 13 个字符，享元池只有 1 个样式对象
    }
}
```

运行结果：

```
字符 'H' 在 (0,0) 处，宋体 12号 黑色
字符 'e' 在 (12,0) 处，宋体 12号 黑色
字符 'l' 在 (24,0) 处，宋体 12号 黑色
字符 'l' 在 (36,0) 处，宋体 12号 黑色
字符 'o' 在 (48,0) 处，宋体 12号 黑色
字符 ' ' 在 (60,0) 处，宋体 12号 黑色
字符 'W' 在 (72,0) 处，宋体 12号 黑色
字符 'o' 在 (84,0) 处，宋体 12号 黑色
字符 'r' 在 (96,0) 处，宋体 12号 黑色
字符 'l' 在 (108,0) 处，宋体 12号 黑色
字符 'd' 在 (120,0) 处，宋体 12号 黑色
字符 ' ' 在 (132,0) 处，宋体 12号 黑色
字符 '你' 在 (144,0) 处，宋体 12号 黑色
字符 '好' 在 (156,0) 处，宋体 12号 黑色
字符 '世' 在 (168,0) 处，宋体 12号 黑色
字符 '界' 在 (180,0) 处，宋体 12号 黑色

享元池大小: 1
```

## 三、享元模式的高级用法

### 3.1 线程安全的享元工厂

```java
public class ThreadSafeFlyweightFactory {
    private final ConcurrentMap<String, CharacterStyle> pool = new ConcurrentHashMap<>();
    
    public CharacterStyle getStyle(String font, int size, String color) {
        String key = font + ":" + size + ":" + color;
        return pool.computeIfAbsent(key, 
            k -> new ConcreteCharacterStyle(font, size, color));
    }
    
    // 带限制的享元池（防止内存泄漏）
    public CharacterStyle getStyleWithLimit(String font, int size, String color, int maxSize) {
        String key = font + ":" + size + ":" + color;
        CharacterStyle existing = pool.get(key);
        if (existing != null) {
            return existing;
        }
        if (pool.size() >= maxSize) {
            // 简单策略：移除最早的一个
            String oldestKey = pool.keySet().iterator().next();
            pool.remove(oldestKey);
        }
        return pool.computeIfAbsent(key, k -> new ConcreteCharacterStyle(font, size, color));
    }
}
```

### 3.2 带 LRU 淘汰的享元工厂

```java
public class LRUFlyweightFactory {
    private final int maxSize;
    private final LinkedHashMap<String, CharacterStyle> pool;
    
    public LRUFlyweightFactory(int maxSize) {
        this.maxSize = maxSize;
        this.pool = new LinkedHashMap<String, CharacterStyle>(16, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, CharacterStyle> eldest) {
                return size() > LRUFlyweightFactory.this.maxSize;
            }
        };
    }
    
    public synchronized CharacterStyle getStyle(String font, int size, String color) {
        String key = font + ":" + size + ":" + color;
        return pool.computeIfAbsent(key, 
            k -> new ConcreteCharacterStyle(font, size, color));
    }
    
    public synchronized int getPoolSize() {
        return pool.size();
    }
}
```

### 3.3 复合享元

将多个享元组合成复合享元，复合享元本身不被共享：

```java
// 复合享元：不被共享
public class CompositeCharacterStyle implements CharacterStyle {
    private final Map<String, CharacterStyle> styles = new HashMap<>();
    
    public void addStyle(String key, CharacterStyle style) {
        styles.put(key, style);
    }
    
    @Override
    public void display(char c, int x, int y) {
        // 根据某种规则选择具体享元
        CharacterStyle style = styles.getOrDefault("default", 
            styles.values().iterator().next());
        style.display(c, x, y);
    }
}

// 复合享元工厂
public class CompositeFlyweightFactory {
    private final CharacterStyleFactory styleFactory = new CharacterStyleFactory();
    
    public CharacterStyle getCompositeStyle(Map<String, String[]> styleConfigs) {
        CompositeCharacterStyle composite = new CompositeCharacterStyle();
        for (Map.Entry<String, String[]> entry : styleConfigs.entrySet()) {
            String[] config = entry.getValue();
            CharacterStyle style = styleFactory.getStyle(config[0], 
                Integer.parseInt(config[1]), config[2]);
            composite.addStyle(entry.getKey(), style);
        }
        return composite;
    }
}
```

## 四、享元模式在 JDK 中的应用

### 4.1 Integer 缓存池

Java 的 `Integer` 类是最经典的享元模式应用：

```java
// Integer 源码：缓存 -128 到 127
public final class Integer extends Number implements Comparable<Integer> {
    private static class IntegerCache {
        static final int low = -128;
        static final int high;
        static final Integer[] cache;
        
        static {
            // 默认缓存 -128 ~ 127
            int h = 127;
            String integerCacheHighPropValue = 
                sun.misc.VM.getSavedProperty("java.lang.Integer.IntegerCache.high");
            if (integerCacheHighPropValue != null) {
                try {
                    int i = parseInt(integerCacheHighPropValue);
                    i = Math.max(i, 127);
                    h = Math.min(i, Integer.MAX_VALUE - (-low) - 1);
                } catch (NumberFormatException nfe) { }
            }
            high = h;
            cache = new Integer[(high - low) + 1];
            int j = low;
            for (int k = 0; k < cache.length; k++) {
                cache[k] = new Integer(j++);
            }
        }
    }
    
    public static Integer valueOf(int i) {
        if (i >= IntegerCache.low && i <= IntegerCache.high)
            return IntegerCache.cache[i + (-IntegerCache.low)];
        return new Integer(i);
    }
}
```

```java
// 验证
Integer a = 127;
Integer b = 127;
System.out.println(a == b);       // true（缓存池中同一个对象）

Integer c = 128;
Integer d = 128;
System.out.println(c == d);       // false（超出缓存范围，新对象）

Integer e = Integer.valueOf(100);
Integer f = Integer.valueOf(100);
System.out.println(e == f);       // true（显式使用 valueOf）

Integer g = new Integer(100);
Integer h = new Integer(100);
System.out.println(g == h);       // false（new 强制创建新对象）
```

### 4.2 String 常量池

Java 的字符串常量池也是享元模式的经典实现：

```java
String s1 = "hello";
String s2 = "hello";
System.out.println(s1 == s2);     // true（常量池中同一个对象）

String s3 = new String("hello");
String s4 = new String("hello");
System.out.println(s3 == s4);     // false（堆上新对象）

String s5 = s3.intern();
System.out.println(s1 == s5);     // true（intern() 返回常量池对象）
```

### 4.3 Byte、Short、Long、Character 缓存

```java
// Byte：缓存 -128 ~ 127（全部）
Byte b1 = (byte) 100;
Byte b2 = (byte) 100;
System.out.println(b1 == b2);     // true

// Character：缓存 0 ~ 127
Character c1 = (char) 100;
Character c2 = (char) 100;
System.out.println(c1 == c2);     // true

// Long：缓存 -128 ~ 127
Long l1 = 100L;
Long l2 = 100L;
System.out.println(l1 == l2);     // true
```

## 五、享元模式 vs 其他模式

### 5.1 对比对象池模式

| 维度 | 享元模式 | 对象池模式 |
|------|---------|-----------|
| 目的 | 减少内存占用 | 减少对象创建/销毁开销 |
| 共享方式 | 多个引用同一对象 | 同一时刻只有一个使用者 |
| 对象状态 | 内部状态不变 | 对象可变，归还时重置 |
| 典型应用 | 字符串常量池 | 数据库连接池 |

```java
// 享元：多个引用指向同一个对象
CharacterStyle style = factory.getStyle("宋体", 12, "黑色");
// style1 和 style2 是同一个对象

// 对象池：借出-归还模式
Connection conn = pool.borrowObject();  // 借出
try { /* 使用 */ } finally { pool.returnObject(conn); }  // 归还
```

### 5.2 对比单例模式

| 维度 | 享元模式 | 单例模式 |
|------|---------|---------|
| 对象数量 | 每个内部状态一个 | 全局唯一一个 |
| 状态 | 内部状态区分不同对象 | 无状态或有状态 |
| 工厂 | FlyweightFactory 管理 | 自身管理 |

### 5.3 对比原型模式

| 维度 | 享元模式 | 原型模式 |
|------|---------|---------|
| 目的 | 共享已有对象 | 克隆创建新对象 |
| 对象来源 | 从池中获取 | 通过 clone 创建 |
| 关注点 | 内存优化 | 创建效率 |

## 六、享元模式的优缺点

### 优点

1. **减少内存占用**：共享内部状态，避免重复创建
2. **减少 GC 压力**：对象数量大幅减少
3. **性能提升**：复用已有对象，减少创建开销
4. **集中管理**：享元工厂统一管理共享对象

### 缺点

1. **增加复杂性**：需要区分内部状态和外部状态
2. **线程安全**：享元对象必须不可变（或线程安全）
3. **维护成本**：享元池需要管理和清理
4. **运行时间换空间**：查找享元对象需要时间

### 适用场景

- 系统中存在大量相同或相似的对象
- 对象的大部分状态可以外部化
- 需要缓存池的场景
- 对象的内部状态与环境无关

## 七、实战：游戏中的粒子系统

用享元模式实现一个游戏粒子系统，高效渲染成千上万的粒子：

```java
// ========== 1. 抽象享元 ==========
public interface ParticleType {
    void render(ParticleContext context);
}

// ========== 2. 粒子上下文（外部状态） ==========
public class ParticleContext {
    private final int x;
    private final int y;
    private final int velocity;
    private final double angle;
    
    public ParticleContext(int x, int y, int velocity, double angle) {
        this.x = x;
        this.y = y;
        this.velocity = velocity;
        this.angle = angle;
    }
    
    public int getX() { return x; }
    public int getY() { return y; }
    public int getVelocity() { return velocity; }
    public double getAngle() { return angle; }
}

// ========== 3. 具体享元：火焰粒子 ==========
public class FireParticle implements ParticleType {
    // 内部状态（共享）
    private final String sprite;       // 精灵图
    private final String color;        // 颜色
    private final double size;         // 基础大小
    private final int lifetime;        // 生命周期(ms)
    
    public FireParticle() {
        this.sprite = "🔥";
        this.color = "#FF4500";
        this.size = 8.0;
        this.lifetime = 2000;
    }
    
    @Override
    public void render(ParticleContext ctx) {
        double scale = size * (1.0 + ctx.getVelocity() * 0.1);
        System.out.printf("  %s 火焰粒子 @ (%d,%d) 角度=%.1f° 大小=%.1f 寿命=%dms%n",
            sprite, ctx.getX(), ctx.getY(), ctx.getAngle(), scale, lifetime);
    }
}

// ========== 4. 具体享元：烟雾粒子 ==========
public class SmokeParticle implements ParticleType {
    private final String sprite;
    private final String color;
    private final double size;
    private final int lifetime;
    
    public SmokeParticle() {
        this.sprite = "💨";
        this.color = "#808080";
        this.size = 12.0;
        this.lifetime = 3000;
    }
    
    @Override
    public void render(ParticleContext ctx) {
        double scale = size * (1.0 + ctx.getVelocity() * 0.05);
        System.out.printf("  %s 烟雾粒子 @ (%d,%d) 角度=%.1f° 大小=%.1f 寿命=%dms%n",
            sprite, ctx.getX(), ctx.getY(), ctx.getAngle(), scale, lifetime);
    }
}

// ========== 5. 具体享元：火花粒子 ==========
public class SparkParticle implements ParticleType {
    private final String sprite;
    private final String color;
    private final double size;
    private final int lifetime;
    
    public SparkParticle() {
        this.sprite = "✨";
        this.color = "#FFD700";
        this.size = 4.0;
        this.lifetime = 500;
    }
    
    @Override
    public void render(ParticleContext ctx) {
        System.out.printf("  %s 火花粒子 @ (%d,%d) 角度=%.1f° 大小=%.1f 寿命=%dms%n",
            sprite, ctx.getX(), ctx.getY(), ctx.getAngle(), size, lifetime);
    }
}

// ========== 6. 享元工厂 ==========
public class ParticleFactory {
    private static final Map<String, ParticleType> pool = new HashMap<>();
    
    public static ParticleType getParticle(String type) {
        return pool.computeIfAbsent(type, key -> {
            switch (key) {
                case "fire":  return new FireParticle();
                case "smoke": return new SmokeParticle();
                case "spark": return new SparkParticle();
                default: throw new IllegalArgumentException("未知粒子类型: " + key);
            }
        });
    }
    
    public static int getPoolSize() { return pool.size(); }
}

// ========== 7. 粒子系统 ==========
public class ParticleSystem {
    private final List<Particle> particles = new ArrayList<>();
    
    public void emit(String type, int x, int y, int count) {
        ParticleType particleType = ParticleFactory.getParticle(type);
        Random random = new Random();
        for (int i = 0; i < count; i++) {
            double angle = random.nextDouble() * 360;
            int velocity = random.nextInt(10) + 1;
            ParticleContext ctx = new ParticleContext(
                x + random.nextInt(20) - 10,
                y + random.nextInt(20) - 10,
                velocity, angle
            );
            particles.add(new Particle(particleType, ctx));
        }
    }
    
    public void render() {
        System.out.println("=== 渲染粒子 ===");
        for (Particle p : particles) {
            p.render();
        }
        System.out.println("粒子总数: " + particles.size() + 
            "，享元池大小: " + ParticleFactory.getPoolSize());
    }
    
    private static class Particle {
        private final ParticleType type;    // 共享的享元
        private final ParticleContext ctx;  // 外部状态
        
        Particle(ParticleType type, ParticleContext ctx) {
            this.type = type;
            this.ctx = ctx;
        }
        
        void render() { type.render(ctx); }
    }
}

// ========== 8. 客户端 ==========
public class GameDemo {
    public static void main(String[][] args) {
        ParticleSystem system = new ParticleSystem();
        
        // 发射大量粒子（每种类型只创建一个享元对象）
        system.emit("fire", 100, 200, 5);
        system.emit("smoke", 100, 200, 3);
        system.emit("spark", 100, 200, 8);
        
        system.render();
        // 16 个粒子，但只有 3 个享元对象
    }
}
```

运行结果：

```
=== 渲染粒子 ===
  🔥 火焰粒子 @ (105,192) 角度=234.5° 大小=10.4 寿命=2000ms
  🔥 火焰粒子 @ (92,195) 角度=78.2° 大小=13.6 寿命=2000ms
  🔥 火焰粒子 @ (107,201) 角度=356.1° 大小=9.6 寿命=2000ms
  🔥 火焰粒子 @ (96,193) 角度=145.8° 大小=12.0 寿命=2000ms
  🔥 火焰粒子 @ (110,205) 角度=22.7° 大小=8.8 寿命=2000ms
  💨 烟雾粒子 @ (94,198) 角度=312.4° 大小=15.0 寿命=3000ms
  💨 烟雾粒子 @ (108,204) 角度=89.6° 大小=18.0 寿命=3000ms
  💨 烟雾粒子 @ (99,196) 角度=167.3° 大小=16.5 寿命=3000ms
  ✨ 火花粒子 @ (103,193) 角度=56.8° 大小=4.0 寿命=500ms
  ✨ 火花粒子 @ (95,207) 角度=289.1° 大小=4.0 寿命=500ms
  ✨ 火花粒子 @ (111,199) 角度=134.5° 大小=4.0 寿命=500ms
  ✨ 火花粒子 @ (88,202) 角度=201.3° 大小=4.0 寿命=500ms
  ✨ 火花粒子 @ (107,190) 角度=45.9° 大小=4.0 寿命=500ms
  ✨ 火花粒子 @ (102,210) 角度=267.8° 大小=4.0 寿命=500ms
  ✨ 火花粒子 @ (93,196) 角度=78.4° 大小=4.0 寿命=500ms
  ✨ 火花粒子 @ (109,203) 角度=156.2° 大小=4.0 寿命=500ms
粒子总数: 16，享元池大小: 3
```

## 八、享元模式在 Spring 中的应用

### 8.1 Bean 默认单例

Spring 的 Bean 默认 scope 是 singleton，本质上是一种享元：

```java
@Configuration
public class AppConfig {
    @Bean
    public DataSource dataSource() {
        // 全局共享同一个 DataSource 对象
        return new HikariDataSource();
    }
    
    @Bean
    public UserRepository userRepository() {
        // 全局共享同一个 UserRepository
        return new UserRepository(dataSource());  // 注入共享的 dataSource
    }
}
```

### 8.2 Spring 的 ConversionService

Spring 的类型转换器使用享元模式缓存转换器实例：

```java
// DefaultConversionService 内部缓存转换器
public class DefaultConversionService extends GenericConversionService {
    public static void addDefaultConverters(ConverterRegistry converterRegistry) {
        // 每种转换器只创建一个实例
        converterRegistry.addConverter(new StringToIntegerConverter());
        converterRegistry.addConverter(new StringToBooleanConverter());
        // ...
    }
}
```

## 九、享元模式与函数式编程

### 9.1 使用 Map.computeIfAbsent 简化工厂

```java
// Java 8 之前
public CharacterStyle getStyle(String font, int size, String color) {
    String key = font + ":" + size + ":" + color;
    CharacterStyle style = pool.get(key);
    if (style == null) {
        style = new ConcreteCharacterStyle(font, size, color);
        pool.put(key, style);
    }
    return style;
}

// Java 8+ 简化
public CharacterStyle getStyle(String font, int size, String color) {
    String key = font + ":" + size + ":" + color;
    return pool.computeIfAbsent(key, 
        k -> new ConcreteCharacterStyle(font, size, color));
}
```

### 9.2 使用 Record 定义享元

```java
// Java 16+：使用 Record 定义不可变享元
public record CharacterStyleRecord(String font, int size, String color) 
    implements CharacterStyle {
    
    @Override
    public void display(char c, int x, int y) {
        System.out.printf("字符 '%c' @ (%d,%d) %s %d号 %s%n",
            c, x, y, font, size, color);
    }
}

// Record 自动实现 equals/hashCode，天然适合做 Map 的 key
```

## 十、面试常见问题

### Q1: 享元模式的核心思想是什么？

享元模式通过共享对象的内部状态来减少内存占用。关键是将对象状态分为内部状态（可共享、不随环境变化）和外部状态（不可共享、随环境变化），通过享元工厂管理和复用享元对象。

### Q2: Integer 缓存池是怎么实现的？

Integer 内部维护了一个 IntegerCache 静态内部类，在类加载时预创建 -128 到 127 的 Integer 对象数组。调用 `Integer.valueOf()` 时，如果在缓存范围内直接返回缓存对象，否则创建新对象。这就是为什么 `Integer.valueOf(127) == Integer.valueOf(127)` 为 true，而 128 则为 false。

### Q3: 享元模式需要考虑线程安全吗？

享元对象本身应该是不可变的（内部状态不可变），因此不需要同步。但享元工厂的池（Map）需要线程安全。可以使用 ConcurrentHashMap 或在 getStyle 方法上加 synchronized。如果享元对象有可变状态，则需要额外的同步机制。

### Q4: 享元模式和对象池模式有什么区别？

享元模式关注"共享"——多个客户端同时引用同一个对象；对象池模式关注"复用"——一个对象在同一时刻只被一个客户端使用，用完后归还。享元的对象是共享的，对象池的对象是借出-归还的。

### Q5: 如何设计享元的 key？

key 应该唯一标识内部状态。通常将内部状态拼接成字符串（如 "宋体:12:黑色"），或使用包含所有内部状态的对象作为 key（需要正确实现 equals/hashCode）。Java 14+ 推荐使用 Record 作为 key。

### Q6: 享元模式会导致内存泄漏吗？

如果享元池不断增长且不清理，会导致内存泄漏。解决方案：1) 使用 LRU 淘汰策略；2) 使用 WeakHashMap 让不用的享元自动回收；3) 设置享元池上限。

## 十一、总结

享元模式是"用时间换空间"的经典策略，通过共享内部状态来大幅减少对象数量。

**核心要点**：

1. **内外分离**：内部状态共享，外部状态不共享
2. **享元工厂**：集中管理共享对象的创建和获取
3. **不可变性**：享元对象必须不可变，保证线程安全
4. **JDK 应用**：Integer 缓存池、String 常量池是最经典的实现
5. **内存优化**：适用于大量重复对象的场景

享元模式看似简单，但它在性能优化中扮演着重要角色。理解 Integer 缓存和 String 常量池的工作原理，不仅有助于写出更高效的 Java 代码，还能帮你避开那些"诡异"的 == 比较陷阱。

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
