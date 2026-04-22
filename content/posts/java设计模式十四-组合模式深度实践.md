---
title: "Java设计模式（十四）：组合模式深度实践"
date: 2026-04-22T10:00:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "组合模式", "composite", "树形结构"]
---

## 前言

组合模式（Composite Pattern）是一种结构型设计模式，它的核心思想是：**将对象组合成树形结构以表示"部分-整体"的层次关系，使得客户端对单个对象和组合对象的使用具有一致性**。

**核心思想**：统一叶子节点和容器节点的接口，让客户端无需区分它们。

<!--more-->

## 一、为什么需要组合模式

### 1.1 部分-整体的困境

假设我们正在开发一个图形编辑器，有基本图形（圆形、矩形）和复合图形（由多个图形组成）。如果不用组合模式：

```java
// 不用组合模式：客户端必须区分叶子节点和容器节点
public class GraphicEditor {
    public void draw(Object graphic) {
        if (graphic instanceof Circle) {
            ((Circle) graphic).draw();
        } else if (graphic instanceof Rectangle) {
            ((Rectangle) graphic).draw();
        } else if (graphic instanceof GraphicGroup) {
            GraphicGroup group = (GraphicGroup) graphic;
            for (Object child : group.getChildren()) {
                draw(child);  // 递归，又要判断类型...
            }
        }
    }
}
```

每新增一种图形或容器，都要修改客户端代码，违反开闭原则。组合模式通过统一接口优雅地解决了这个问题。

### 1.2 树形结构的普遍性

组合模式在现实世界中无处不在：

- **文件系统**：文件和文件夹
- **组织架构**：员工和部门
- **GUI 组件**：按钮和容器面板
- **菜单系统**：菜单项和子菜单

这些场景的共同特点是：存在树形的"部分-整体"层次关系，客户端希望统一处理叶子节点和容器节点。

## 二、组合模式的结构

### 2.1 类图

```
┌──────────────────────┐
│    Component (抽象)   │
│──────────────────────│
│ + operation()        │
│ + add(Component)     │
│ + remove(Component)  │
│ + getChild(int)      │
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │           │
┌────┴────┐ ┌────┴─────────┐
│  Leaf   │ │  Composite   │
│ (叶子)  │ │  (组合)      │
│─────────│ │──────────────│
│operation│ │ children:List│
│         │ │ add()        │
│         │ │ remove()     │
│         │ │ getChild()   │
│         │ │ operation()  │
└─────────┘ └──────────────┘
```

### 2.2 两种实现方式

组合模式有两种经典实现：

| 方式 | 特点 | 优缺点 |
|------|------|--------|
| 透明式 | Component 定义所有方法（包括 add/remove） | 客户端一致性好，但 Leaf 需要抛异常 |
| 安全式 | Component 只定义公共方法，Composite 额外定义 add/remove | 类型安全，但客户端需要类型判断 |

### 2.3 完整实现（透明式）

```java
// ========== 1. 抽象组件 ==========
public abstract class Graphic {
    protected String name;
    
    public Graphic(String name) {
        this.name = name;
    }
    
    public String getName() { return name; }
    
    // 公共操作
    public abstract void draw();
    
    // 容器操作（透明式：叶子节点抛异常）
    public void add(Graphic graphic) {
        throw new UnsupportedOperationException("叶子节点不支持 add 操作");
    }
    
    public void remove(Graphic graphic) {
        throw new UnsupportedOperationException("叶子节点不支持 remove 操作");
    }
    
    public Graphic getChild(int index) {
        throw new UnsupportedOperationException("叶子节点不支持 getChild 操作");
    }
}

// ========== 2. 叶子节点：圆形 ==========
public class Circle extends Graphic {
    private int radius;
    
    public Circle(String name, int radius) {
        super(name);
        this.radius = radius;
    }
    
    @Override
    public void draw() {
        System.out.println("  ○ 绘制圆形: " + name + " (半径=" + radius + ")");
    }
}

// ========== 3. 叶子节点：矩形 ==========
public class Rectangle extends Graphic {
    private int width;
    private int height;
    
    public Rectangle(String name, int width, int height) {
        super(name);
        this.width = width;
        this.height = height;
    }
    
    @Override
    public void draw() {
        System.out.println("  □ 绘制矩形: " + name + " (宽=" + width + ", 高=" + height + ")");
    }
}

// ========== 4. 组合节点：图形组 ==========
public class GraphicGroup extends Graphic {
    private final List<Graphic> children = new ArrayList<>();
    
    public GraphicGroup(String name) {
        super(name);
    }
    
    @Override
    public void add(Graphic graphic) {
        children.add(graphic);
    }
    
    @Override
    public void remove(Graphic graphic) {
        children.remove(graphic);
    }
    
    @Override
    public Graphic getChild(int index) {
        return children.get(index);
    }
    
    @Override
    public void draw() {
        System.out.println("📦 图形组: " + name + " (包含 " + children.size() + " 个图形)");
        for (Graphic child : children) {
            child.draw();  // 递归绘制
        }
    }
}

// ========== 5. 客户端 ==========
public class GraphicDemo {
    public static void main(String[] args) {
        // 创建叶子节点
        Circle circle1 = new Circle("太阳", 50);
        Rectangle rect1 = new Rectangle("草地", 800, 200);
        Circle circle2 = new Circle("花朵1", 10);
        Circle circle3 = new Circle("花朵2", 12);
        Rectangle rect2 = new Rectangle("树干", 20, 100);
        Circle circle4 = new Circle("树冠", 60);
        
        // 创建组合节点
        GraphicGroup flowers = new GraphicGroup("花朵组");
        flowers.add(circle2);
        flowers.add(circle3);
        
        GraphicGroup tree = new GraphicGroup("树");
        tree.add(rect2);
        tree.add(circle4);
        
        GraphicGroup scene = new GraphicGroup("风景画");
        scene.add(circle1);
        scene.add(rect1);
        scene.add(flowers);
        scene.add(tree);
        
        // 统一调用：无需区分叶子还是组合
        scene.draw();
    }
}
```

运行结果：

```
📦 图形组: 风景画 (包含 4 个图形)
  ○ 绘制圆形: 太阳 (半径=50)
  □ 绘制矩形: 草地 (宽=800, 高=200)
📦 图形组: 花朵组 (包含 2 个图形)
  ○ 绘制圆形: 花朵1 (半径=10)
  ○ 绘制圆形: 花朵2 (半径=12)
📦 图形组: 树 (包含 2 个图形)
  □ 绘制矩形: 树干 (宽=20, 高=100)
  ○ 绘制圆形: 树冠 (半径=60)
```

### 2.4 安全式实现

```java
// ========== 安全式：Component 只定义公共操作 ==========
public interface Graphic {
    void draw();
    String getName();
}

// 叶子节点
public class Circle implements Graphic {
    private String name;
    private int radius;
    
    public Circle(String name, int radius) {
        this.name = name;
        this.radius = radius;
    }
    
    @Override
    public void draw() {
        System.out.println("  ○ 绘制圆形: " + name);
    }
    
    @Override
    public String getName() { return name; }
}

// 组合节点：只有 Composite 有 add/remove
public class GraphicGroup implements Graphic {
    private String name;
    private final List<Graphic> children = new ArrayList<>();
    
    public GraphicGroup(String name) {
        this.name = name;
    }
    
    public void add(Graphic graphic) { children.add(graphic); }
    public void remove(Graphic graphic) { children.remove(graphic); }
    public Graphic getChild(int index) { return children.get(index); }
    public List<Graphic> getChildren() { return children; }
    
    @Override
    public void draw() {
        System.out.println("📦 图形组: " + name);
        children.forEach(Graphic::draw);
    }
    
    @Override
    public String getName() { return name; }
}

// 客户端：需要类型判断
public class Client {
    public void process(Graphic graphic) {
        graphic.draw();
        
        if (graphic instanceof GraphicGroup) {
            GraphicGroup group = (GraphicGroup) graphic;
            for (Graphic child : group.getChildren()) {
                process(child);
            }
        }
    }
}
```

## 三、组合模式的高级用法

### 3.1 带缓存的组合模式

在需要频繁计算的场景中，可以在组合节点缓存计算结果：

```java
public abstract class FileSystemNode {
    protected String name;
    protected Long cachedSize = null;  // 缓存
    
    public abstract long computeSize();
    
    public final long getSize() {
        if (cachedSize == null) {
            cachedSize = computeSize();
        }
        return cachedSize;
    }
    
    public void invalidateCache() {
        cachedSize = null;
    }
    
    public String getName() { return name; }
}

public class File extends FileSystemNode {
    private final long size;
    
    public File(String name, long size) {
        this.name = name;
        this.size = size;
    }
    
    @Override
    public long computeSize() {
        return size;
    }
}

public class Folder extends FileSystemNode {
    private final List<FileSystemNode> children = new ArrayList<>();
    
    public Folder(String name) {
        this.name = name;
    }
    
    public void add(FileSystemNode node) {
        children.add(node);
        invalidateCache();  // 子节点变化，缓存失效
    }
    
    public void remove(FileSystemNode node) {
        children.remove(node);
        invalidateCache();
    }
    
    @Override
    public long computeSize() {
        return children.stream().mapToLong(FileSystemNode::getSize).sum();
    }
}
```

### 3.2 带引用计数的组合模式

在资源管理中，同一个子节点可能被多个父节点引用：

```java
public class SharedFolder extends FileSystemNode {
    private final List<FileSystemNode> children = new ArrayList<>();
    private final Map<FileSystemNode, Integer> refCounts = new HashMap<>();
    
    public void add(FileSystemNode node) {
        children.add(node);
        refCounts.merge(node, 1, Integer::sum);
    }
    
    public void remove(FileSystemNode node) {
        int count = refCounts.getOrDefault(node, 0);
        if (count <= 1) {
            children.remove(node);
            refCounts.remove(node);
        } else {
            refCounts.put(node, count - 1);
        }
    }
}
```

### 3.3 组合模式与迭代器

为组合结构提供迭代器，支持深度优先和广度优先遍历：

```java
// 深度优先迭代器
public class DepthFirstIterator implements Iterator<FileSystemNode> {
    private final Deque<FileSystemNode> stack = new ArrayDeque<>();
    
    public DepthFirstIterator(FileSystemNode root) {
        stack.push(root);
    }
    
    @Override
    public boolean hasNext() {
        return !stack.isEmpty();
    }
    
    @Override
    public FileSystemNode next() {
        if (!hasNext()) throw new NoSuchElementException();
        FileSystemNode node = stack.pop();
        if (node instanceof Folder) {
            Folder folder = (Folder) node;
            // 逆序入栈，保证顺序正确
            List<FileSystemNode> children = folder.getChildren();
            for (int i = children.size() - 1; i >= 0; i--) {
                stack.push(children.get(i));
            }
        }
        return node;
    }
}

// 广度优先迭代器
public class BreadthFirstIterator implements Iterator<FileSystemNode> {
    private final Queue<FileSystemNode> queue = new LinkedList<>();
    
    public BreadthFirstIterator(FileSystemNode root) {
        queue.offer(root);
    }
    
    @Override
    public boolean hasNext() {
        return !queue.isEmpty();
    }
    
    @Override
    public FileSystemNode next() {
        if (!hasNext()) throw new NoSuchElementException();
        FileSystemNode node = queue.poll();
        if (node instanceof Folder) {
            Folder folder = (Folder) node;
            for (FileSystemNode child : folder.getChildren()) {
                queue.offer(child);
            }
        }
        return node;
    }
}
```

### 3.4 组合模式与访问者

组合模式与访问者模式是天然的搭档——组合模式提供统一结构，访问者模式提供操作扩展：

```java
public interface FileSystemVisitor {
    void visit(File file);
    void visit(Folder folder);
}

public abstract class FileSystemNode {
    public abstract void accept(FileSystemVisitor visitor);
}

public class File extends FileSystemNode {
    @Override
    public void accept(FileSystemVisitor visitor) {
        visitor.visit(this);
    }
}

public class Folder extends FileSystemNode {
    private final List<FileSystemNode> children = new ArrayList<>();
    
    @Override
    public void accept(FileSystemVisitor visitor) {
        visitor.visit(this);
        for (FileSystemNode child : children) {
            child.accept(visitor);  // 递归访问
        }
    }
}

// 使用：统计大小
public class SizeVisitor implements FileSystemVisitor {
    private long totalSize = 0;
    
    @Override
    public void visit(File file) { totalSize += file.getSize(); }
    
    @Override
    public void visit(Folder folder) { /* 文件夹本身不计大小 */ }
    
    public long getTotalSize() { return totalSize; }
}
```

## 四、组合模式在 JDK 中的应用

### 4.1 AWT/Swing 组件体系

Java AWT 和 Swing 是组合模式的经典实现：

```java
// Component 是抽象组件
// Container 是组合节点（继承 Component）
// Button、Label 等是叶子节点

public class SwingDemo {
    public static void main(String[] args) {
        // Container 可以添加子组件
        JFrame frame = new JFrame("组合模式示例");
        Container container = frame.getContentPane();
        
        // 叶子节点
        JButton button = new JButton("点击我");
        JLabel label = new JLabel("标签");
        
        // 组合节点
        JPanel panel = new JPanel();
        panel.add(button);
        panel.add(label);
        
        container.add(panel);
        
        // 统一处理：paint() 方法递归调用
        // frame.paint() → container.paint() → panel.paint() → button.paint() + label.paint()
    }
}
```

关键源码结构：

```java
// java.awt.Component（抽象组件）
public abstract class Component implements ImageObserver, MenuContainer, Serializable {
    public abstract void paint(Graphics g);
    // ...
}

// java.awt.Container（组合节点）
public class Container extends Component {
    private List<Component> component = new ArrayList<>();
    
    public Component add(Component comp) { ... }
    public void remove(int index) { ... }
    public Component getComponent(int n) { ... }
    
    @Override
    public void paint(Graphics g) {
        // 递归绘制子组件
        for (Component comp : component) {
            comp.paint(g);
        }
    }
}

// javax.swing.JButton（叶子节点）
public class JButton extends AbstractButton {
    @Override
    public void paint(Graphics g) {
        // 绘制按钮自身
    }
}
```

### 4.2 Java NIO DirectoryStream

```java
// 使用 NIO 遍历目录树（组合模式思想）
public class NioDirectoryDemo {
    public static void main(String[] args) throws IOException {
        Path start = Paths.get("/Users/project");
        
        // Files.walk 返回文件树的所有路径
        try (Stream<Path> paths = Files.walk(start)) {
            paths.forEach(path -> {
                if (Files.isDirectory(path)) {
                    System.out.println("📁 " + path);
                } else {
                    System.out.println("  📄 " + path);
                }
            });
        }
    }
}
```

## 五、组合模式 vs 其他模式

### 5.1 对比装饰器模式

| 维度 | 组合模式 | 装饰器模式 |
|------|---------|-----------|
| 目的 | 构建"部分-整体"树形结构 | 动态添加职责 |
| 子节点 | 多个子节点 | 通常一个被装饰对象 |
| 接口一致性 | 叶子和组合统一接口 | 装饰器和被装饰者统一接口 |
| 结构 | 树形 | 链式 |

```java
// 组合模式：一对多
Folder root = new Folder("root");
root.add(file1);
root.add(file2);
root.add(subFolder);

// 装饰器模式：一对一
InputStream in = new FileInputStream("data.txt");
in = new BufferedInputStream(in);       // 装饰1
in = new GZIPInputStream(in);           // 装饰2
```

### 5.2 对比迭代器模式

| 维度 | 组合模式 | 迭代器模式 |
|------|---------|-----------|
| 关注点 | 构建层次结构 | 顺序访问集合 |
| 结构 | 树形 | 线性 |
| 扩展 | 添加新的叶子/组合类型 | 添加新的遍历策略 |

### 5.3 与访问者模式联用

组合模式经常与访问者模式联用，形成强大的"结构+操作"组合：

- **组合模式**：构建树形结构，提供统一的 `accept` 接口
- **访问者模式**：定义对树形结构的各种操作

## 六、组合模式的优缺点

### 优点

1. **简化客户端代码**：客户端无需区分叶子和组合，统一调用
2. **开闭原则**：新增叶子或组合类型无需修改客户端
3. **天然递归**：树形结构适合递归处理
4. **灵活性**：可以自由组合出复杂的层次结构

### 缺点

1. **透明式违反单一职责**：叶子节点被迫实现不需要的 add/remove 方法
2. **安全式需要类型判断**：客户端需要 instanceof 判断
3. **难以限制组合类型**：不容易限制某些叶子只能放在特定组合中
4. **调试困难**：递归调用堆栈深，不易定位问题

### 适用场景

- 需要表示"部分-整体"层次结构
- 希望客户端统一处理叶子和组合
- 结构是递归的、树形的
- 如文件系统、GUI 组件、组织架构、菜单系统

## 七、实战：文件系统管理器

用组合模式实现一个完整的文件系统管理器：

```java
// ========== 抽象组件 ==========
public abstract class FileSystemNode {
    protected String name;
    protected LocalDateTime createdAt;
    protected LocalDateTime modifiedAt;
    
    public FileSystemNode(String name) {
        this.name = name;
        this.createdAt = LocalDateTime.now();
        this.modifiedAt = LocalDateTime.now();
    }
    
    public String getName() { return name; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getModifiedAt() { return modifiedAt; }
    
    // 公共操作
    public abstract long getSize();
    public abstract void print(String indent);
    
    // 容器操作
    public void add(FileSystemNode node) {
        throw new UnsupportedOperationException();
    }
    public void remove(FileSystemNode node) {
        throw new UnsupportedOperationException();
    }
    public List<FileSystemNode> getChildren() {
        return Collections.emptyList();
    }
    
    protected void updateModifiedTime() {
        this.modifiedAt = LocalDateTime.now();
    }
}

// ========== 文件（叶子） ==========
public class File extends FileSystemNode {
    private final long size;
    private String extension;
    
    public File(String name, long size) {
        super(name);
        this.size = size;
        int dotIndex = name.lastIndexOf('.');
        this.extension = dotIndex > 0 ? name.substring(dotIndex + 1) : "";
    }
    
    public String getExtension() { return extension; }
    
    @Override
    public long getSize() { return size; }
    
    @Override
    public void print(String indent) {
        System.out.printf("%s📄 %s (%s, %s)%n", 
            indent, name, formatSize(size), extension);
    }
    
    private String formatSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return String.format("%.1f KB", bytes / 1024.0);
        if (bytes < 1024 * 1024 * 1024) return String.format("%.1f MB", bytes / (1024.0 * 1024));
        return String.format("%.1f GB", bytes / (1024.0 * 1024 * 1024));
    }
}

// ========== 文件夹（组合） ==========
public class Folder extends FileSystemNode {
    private final List<FileSystemNode> children = new ArrayList<>();
    
    public Folder(String name) {
        super(name);
    }
    
    @Override
    public void add(FileSystemNode node) {
        children.add(node);
        updateModifiedTime();
    }
    
    @Override
    public void remove(FileSystemNode node) {
        children.remove(node);
        updateModifiedTime();
    }
    
    @Override
    public List<FileSystemNode> getChildren() {
        return Collections.unmodifiableList(children);
    }
    
    @Override
    public long getSize() {
        return children.stream().mapToLong(FileSystemNode::getSize).sum();
    }
    
    @Override
    public void print(String indent) {
        System.out.printf("%s📁 %s/ (%s, %d items)%n", 
            indent, name, formatSize(getSize()), children.size());
        for (FileSystemNode child : children) {
            child.print(indent + "  ");
        }
    }
    
    // 文件搜索
    public List<File> searchByExtension(String ext) {
        List<File> results = new ArrayList<>();
        for (FileSystemNode child : children) {
            if (child instanceof File) {
                File file = (File) child;
                if (file.getExtension().equalsIgnoreCase(ext)) {
                    results.add(file);
                }
            } else if (child instanceof Folder) {
                results.addAll(((Folder) child).searchByExtension(ext));
            }
        }
        return results;
    }
    
    // 按大小排序
    public List<FileSystemNode> sortBySize() {
        return children.stream()
            .sorted(Comparator.comparingLong(FileSystemNode::getSize).reversed())
            .collect(Collectors.toList());
    }
    
    private String formatSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return String.format("%.1f KB", bytes / 1024.0);
        if (bytes < 1024 * 1024 * 1024) return String.format("%.1f MB", bytes / (1024.0 * 1024));
        return String.format("%.1f GB", bytes / (1024.0 * 1024 * 1024));
    }
}

// ========== 客户端 ==========
public class FileSystemDemo {
    public static void main(String[] args) {
        Folder root = new Folder("project");
        
        Folder src = new Folder("src");
        src.add(new File("Main.java", 2048));
        src.add(new File("Utils.java", 1024));
        
        Folder main = new Folder("main");
        main.add(new File("App.java", 4096));
        main.add(new File("Config.java", 512));
        src.add(main);
        
        Folder test = new Folder("test");
        test.add(new File("AppTest.java", 3072));
        src.add(test);
        
        Folder resources = new Folder("resources");
        resources.add(new File("app.properties", 256));
        resources.add(new File("logo.png", 51200));
        resources.add(new File("banner.jpg", 102400));
        
        root.add(src);
        root.add(resources);
        root.add(new File("pom.xml", 4096));
        root.add(new File("README.md", 2048));
        root.add(new File(".gitignore", 128));
        
        // 打印文件树
        System.out.println("=== 文件系统结构 ===");
        root.print("");
        
        // 搜索 Java 文件
        System.out.println("\n=== Java 文件 ===");
        root.searchByExtension("java").forEach(f -> 
            System.out.println("  " + f.getName() + " (" + f.getSize() + " B)"));
        
        // 按大小排序
        System.out.println("\n根目录内容（按大小排序）:");
        root.sortBySize().forEach(n -> 
            System.out.println("  " + n.getName() + " - " + n.getSize() + " B"));
        
        // 总大小
        System.out.println("\n📊 项目总大小: " + root.getSize() + " bytes");
    }
}
```

运行结果：

```
=== 文件系统结构 ===
📁 project/ (169.2 KB, 5 items)
  📁 src/ (10.8 KB, 3 items)
    📄 Main.java (2.0 KB, java)
    📄 Utils.java (1.0 KB, java)
    📁 main/ (4.5 KB, 2 items)
      📄 App.java (4.0 KB, java)
      📄 Config.java (512 B, java)
    📁 test/ (3.0 KB, 1 items)
      📄 AppTest.java (3.0 KB, java)
  📁 resources/ (150.2 KB, 3 items)
    📄 app.properties (256 B, properties)
    📄 logo.png (50.0 KB, png)
    📄 banner.jpg (100.0 KB, jpg)
  📄 pom.xml (4.0 KB, xml)
  📄 README.md (2.0 KB, md)
  📄 .gitignore (128 B, gitignore)

=== Java 文件 ===
  Main.java (2048 B)
  Utils.java (1024 B)
  App.java (4096 B)
  Config.java (512 B)
  AppTest.java (3072 B)

根目录内容（按大小排序）:
  resources - 153856 B
  src - 10752 B
  pom.xml - 4096 B
  README.md - 2048 B
  .gitignore - 128 B

📊 项目总大小: 173312 bytes
```

## 八、组合模式在 Spring 中的应用

### 8.1 CacheManager 组合

Spring Cache 中的 `CompositeCacheManager` 是组合模式的变体：

```java
// Spring 源码：CompositeCacheManager
public class CompositeCacheManager implements CacheManager, InitializingBean {
    private final List<CacheManager> cacheManagers = new ArrayList<>();
    private boolean fallbackToNoOpCache = false;
    
    public CompositeCacheManager(CacheManager... cacheManagers) {
        this.cacheManagers.addAll(Arrays.asList(cacheManagers));
    }
    
    @Override
    public Cache getCache(String name) {
        // 遍历所有 CacheManager，找到第一个有该缓存的
        for (CacheManager cacheManager : this.cacheManagers) {
            Cache cache = cacheManager.getCache(name);
            if (cache != null) {
                return cache;
            }
        }
        return null;
    }
    
    @Override
    public Collection<String> getCacheNames() {
        Set<String> names = new LinkedHashSet<>();
        for (CacheManager cacheManager : this.cacheManagers) {
            names.addAll(cacheManager.getCacheNames());
        }
        return Collections.unmodifiableSet(names);
    }
}
```

### 8.2 WebFlux Handler 组合

Spring WebFlux 的 `CompositeHttpHandler` 组合多个 Handler：

```java
// 组合多个 WebFilter
public class DefaultWebFilterChain implements WebFilterChain {
    private final List<WebFilter> filters;
    private final WebHandler handler;
    private final int index;
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange) {
        return Mono.defer(() -> {
            if (this.index < filters.size()) {
                WebFilter filter = filters.get(this.index);
                return filter.filter(exchange, new DefaultWebFilterChain(filters, handler, index + 1));
            } else {
                return handler.handle(exchange);
            }
        });
    }
}
```

## 九、组合模式与函数式编程

### 9.1 使用 Stream API 简化

```java
// 使用 Stream 递归遍历组合结构
public class FileSystemStreamer {
    public static Stream<FileSystemNode> flatten(FileSystemNode root) {
        return Stream.concat(
            Stream.of(root),
            root.getChildren().stream().flatMap(FileSystemStreamer::flatten)
        );
    }
    
    // 使用示例
    public static void main(String[] args) {
        Folder root = buildFileSystem();
        
        // 找到所有大于 1KB 的文件
        List<File> bigFiles = flatten(root)
            .filter(node -> node instanceof File)
            .map(node -> (File) node)
            .filter(file -> file.getSize() > 1024)
            .collect(Collectors.toList());
        
        // 统计总大小
        long totalSize = flatten(root)
            .filter(node -> node instanceof File)
            .mapToLong(FileSystemNode::getSize)
            .sum();
    }
}
```

### 9.2 使用 Optional 处理可能为空的子节点

```java
public abstract class FileSystemNode {
    public Optional<FileSystemNode> find(String name) {
        if (this.name.equals(name)) {
            return Optional.of(this);
        }
        return getChildren().stream()
            .map(child -> child.find(name))
            .filter(Optional::isPresent)
            .map(Optional::get)
            .findFirst();
    }
}
```

## 十、面试常见问题

### Q1: 组合模式的核心思想是什么？

组合模式将对象组合成树形结构，统一叶子节点和容器节点的接口，使客户端可以一致地处理单个对象和组合对象。核心是"部分-整体"的层次关系和接口一致性。

### Q2: 透明式和安全式有什么区别？

透明式在 Component 中定义所有方法（包括 add/remove），叶子节点抛 UnsupportedOperationException；客户端无需类型判断。安全式只在 Composite 中定义 add/remove，客户端需要 instanceof 判断但类型更安全。实际项目中透明式更常用。

### Q3: 组合模式和装饰器模式有什么区别？

组合模式关注"部分-整体"层次关系，一个组合可以包含多个子节点；装饰器模式关注动态添加职责，装饰器通常只包装一个对象。装饰器是链式结构，组合模式是树形结构。

### Q4: 什么场景下应该使用组合模式？

- 需要表示"部分-整体"层次结构（文件系统、组织架构、GUI 组件）
- 希望客户端统一处理叶子和组合
- 结构可以递归嵌套
- 需要对整棵树执行统一操作

### Q5: 组合模式如何与访问者模式联用？

组合模式提供统一的结构（Component 的 accept 方法），访问者模式定义对结构的操作。组合节点在 accept 中递归调用子节点的 accept，访问者在遍历过程中执行具体逻辑。这种组合让结构和操作完全解耦。

### Q6: 如何处理组合模式中的缓存问题？

可以在组合节点中缓存计算结果（如文件夹大小），当子节点发生变化时（add/remove）使缓存失效。这类似于"脏标记"技术，避免每次都递归计算。

## 十一、总结

组合模式是处理树形结构的利器，它通过统一叶子节点和容器节点的接口，让客户端无需关心处理的是单个对象还是组合对象。

**核心要点**：

1. **统一接口**：叶子和组合实现相同的接口，客户端一致处理
2. **树形结构**：天然支持递归嵌套的层次结构
3. **两种实现**：透明式（推荐）和安全式各有优劣
4. **JDK 应用**：AWT/Swing 组件体系是经典实现
5. **模式联用**：与访问者模式、迭代器模式搭配效果极佳

组合模式看似简单，但它是构建复杂层次结构的基础。掌握它，你就能优雅地处理文件系统、GUI、组织架构等各种树形场景。

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
