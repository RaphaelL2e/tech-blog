---
title: "Java设计模式（十三）：访问者模式深度实践"
date: 2026-04-21T23:20:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "访问者模式", "visitor", "double-dispatch"]
---

## 前言

访问者模式（Visitor Pattern）是 GoF 23 种设计模式中最复杂、最难理解的一个。它的核心思想是：**把对数据结构中每个元素的操作（Visitor）分离出来，允许在不改变元素类的前提下定义新的操作**。

**核心思想**：将数据结构与作用于结构上的操作解耦，新增操作时无需修改数据结构本身。

<!--more-->

## 一、为什么需要访问者模式

### 1.1 开闭原则的终极挑战

假设我们正在开发一个文件系统，有文件（File）和文件夹（Folder）两种元素，我们需要支持多种操作：统计大小、查找文件、打印结构。如果用传统方式：

```java
// 元素基类
public abstract class FileSystemNode {
    String name;
    public abstract void print(int depth);
    public abstract long getSize();
    public abstract boolean search(String keyword);
}
```

每新增一种操作，都需要修改 File 和 Folder 类，违反开闭原则。而访问者模式可以完美解决这个问题。

### 1.2 双重分发的艺术

访问者模式利用了 Java 的**双重分发（Double Dispatch）** 机制：

- **第一次分发**：调用 `element.accept(visitor)`，由元素决定调用哪个 `visitor.visit(this)`
- **第二次分发**：在 `Visitor.visit(ElementA)` 中，实际执行操作

这样，元素的类型决定了调用哪个 visit 方法，而 visit 方法的参数类型又决定了具体执行哪个重载版本。

## 二、访问者模式的结构

### 2.1 类图

```
┌─────────────────┐       ┌──────────────────┐
│    Visitor      │       │ Element (抽象元素) │
│ (抽象访问者)     │       │ (抽象元素)         │
├─────────────────┤       ├──────────────────┤
│ +visit(ElementA)│       │ +accept(Visitor)  │
│ +visit(ElementB)│       └────────┬───────────┘
└────────┬────────┘                │
         │                         │
    ┌────┴────┐              ┌──────┴──────┐
    │         │              │             │
┌───┴───┐ ┌───┴───┐    ┌────┴────┐  ┌─────┴────┐
│ConcrV │ │ConcrV │    │ElementA│  │ElementB  │
│  1    │ │  2    │    └────┬────┘  └────┬─────┘
└───────┘ └───────┘         │             │
                            │             │
                       accept(v)    accept(v)
                            │             │
                         v.visit(this) v.visit(this)
```

### 2.2 核心角色

| 角色 | 职责 |
|------|------|
| Visitor（抽象访问者） | 为每种 Element 声明一个 visit 操作 |
| ConcreteVisitor（具体访问者） | 实现对每个 Element 的具体操作 |
| Element（抽象元素） | 定义 accept 方法，接收一个访问者 |
| ConcreteElement（具体元素） | 实现 accept，调用 visitor 的 visit 方法 |
| ObjectStructure（对象结构） | 包含元素的容器，可迭代访问 |

### 2.3 完整实现

```java
// ========== 1. 抽象元素 ==========
public abstract class FileSystemNode {
    protected String name;
    protected long size;
    
    public FileSystemNode(String name, long size) {
        this.name = name;
        this.size = size;
    }
    
    public String getName() { return name; }
    public long getSize() { return size; }
    
    // 关键：accept 方法接收访问者
    public abstract void accept(FileSystemVisitor visitor);
}

// ========== 2. 具体元素 ==========
public class File extends FileSystemNode {
    public File(String name, long size) {
        super(name, size);
    }
    
    @Override
    public void accept(FileSystemVisitor visitor) {
        // 第二次分发：调用 visitor 对应类型的 visit 方法
        visitor.visit(this);
    }
}

public class Folder extends FileSystemNode {
    private final List<FileSystemNode> children = new ArrayList<>();
    
    public Folder(String name) {
        super(name, 0);
    }
    
    public void add(FileSystemNode node) {
        children.add(node);
        this.size += node.getSize();
    }
    
    public List<FileSystemNode> getChildren() {
        return children;
    }
    
    @Override
    public long getSize() {
        return children.stream().mapToLong(FileSystemNode::getSize).sum();
    }
    
    @Override
    public void accept(FileSystemVisitor visitor) {
        visitor.visit(this);  // 第二次分发
    }
}

// ========== 3. 抽象访问者 ==========
public interface FileSystemVisitor {
    void visit(File file);
    void visit(Folder folder);
}

// ========== 4. 具体访问者：统计大小 ==========
public class SizeCalculatorVisitor implements FileSystemVisitor {
    private long totalSize = 0;
    
    @Override
    public void visit(File file) {
        totalSize += file.getSize();
        System.out.println("  文件: " + file.getName() + " (" + file.getSize() + " bytes)");
    }
    
    @Override
    public void visit(Folder folder) {
        System.out.println("📁 文件夹: " + folder.getName());
        for (FileSystemNode child : folder.getChildren()) {
            child.accept(this);  // 递归遍历
        }
    }
    
    public long getTotalSize() {
        return totalSize;
    }
}

// ========== 5. 具体访问者：查找文件 ==========
public class FileSearchVisitor implements FileSystemVisitor {
    private String keyword;
    private List<File> foundFiles = new ArrayList<>();
    
    public FileSearchVisitor(String keyword) {
        this.keyword = keyword;
    }
    
    @Override
    public void visit(File file) {
        if (file.getName().contains(keyword)) {
            foundFiles.add(file);
        }
    }
    
    @Override
    public void visit(Folder folder) {
        for (FileSystemNode child : folder.getChildren()) {
            child.accept(this);  // 递归
        }
    }
    
    public List<File> getFoundFiles() {
        return foundFiles;
    }
}

// ========== 6. 客户端使用 ==========
public class FileSystemDemo {
    public static void main(String[] args) {
        // 构建文件系统结构
        Folder root = new Folder("root");
        Folder docs = new Folder("docs");
        Folder images = new Folder("images");
        
        File readme = new File("readme.txt", 1024);
        File report = new File("report.pdf", 204800);
        File photo1 = new File("photo1.jpg", 102400);
        File photo2 = new File("photo2.jpg", 153600);
        
        docs.add(readme);
        docs.add(report);
        images.add(photo1);
        images.add(photo2);
        root.add(docs);
        root.add(images);
        
        // 访问者1：统计大小
        SizeCalculatorVisitor sizeVisitor = new SizeCalculatorVisitor();
        root.accept(sizeVisitor);
        System.out.println("\n📊 总大小: " + sizeVisitor.getTotalSize() + " bytes");
        
        // 访问者2：查找文件
        FileSearchVisitor searchVisitor = new FileSearchVisitor("photo");
        root.accept(searchVisitor);
        System.out.println("\n🔍 找到的文件:");
        searchVisitor.getFoundFiles().forEach(f -> 
            System.out.println("  - " + f.getName() + " (" + f.getSize() + " bytes)"));
    }
}
```

运行结果：

```
📁 文件夹: root
📁 文件夹: docs
  文件: readme.txt (1024 bytes)
  文件: report.pdf (204800 bytes)
📁 文件夹: images
  文件: photo1.jpg (102400 bytes)
  文件: photo2.jpg (153600 bytes)

📊 总大小: 461824 bytes

🔍 找到的文件:
  - photo1.jpg (102400 bytes)
  - photo2.jpg (153600 bytes)
```

## 三、双重分发详解

### 3.1 为什么需要双重分发

Java 是静态分派的（方法签名在编译时确定），如果没有双重分发机制：

```java
// ❌ 单分发的问题：无法根据实际类型动态调用
public void process(FileSystemNode node, SizeCalculatorVisitor visitor) {
    // 这里编译器只能确定 Visitor 类型，无法确定 FileSystemNode 的具体子类型
    visitor.visit(node);  // 只能调用 visit(FileSystemNode)，失去多态意义
}

// ✅ 双分发解决方案
public void process(FileSystemNode node, FileSystemVisitor visitor) {
    // 第一次分发：node.accept(this) → 调用 node 的具体 accept
    // accept 内部调用 visitor.visit(this) → 根据 this 的实际类型分发
    node.accept(visitor);
}
```

### 3.2 分发过程图解

```
client.process(root, sizeVisitor)
│
├─ root.accept(sizeVisitor)
│  └─ sizeVisitor.visit(this)  ← this = root (Folder类型)
│     └─ 调用 visit(Folder) ✅
│        └─ 遍历 children，递归调用 child.accept(visitor)
│
├─ child.accept(sizeVisitor)  ← child = docs (Folder类型)
│  └─ sizeVisitor.visit(this)  ← this = docs (Folder类型)
│     └─ 调用 visit(Folder) ✅
│
└─ file.accept(sizeVisitor)  ← file = readme.txt (File类型)
   └─ sizeVisitor.visit(this)  ← this = readme.txt (File类型)
      └─ 调用 visit(File) ✅
```

### 3.3 visit 方法重载 vs @Override

注意 `FileSystemVisitor` 接口中的两个方法：

```java
public interface FileSystemVisitor {
    void visit(File file);      // 重载1
    void visit(Folder folder);  // 重载2
}
```

在 Java 中，方法重载是在**编译时**根据参数静态类型决定的：

```java
FileSystemNode file = new File("test.txt", 100);
visitor.visit(file);  // 编译器认为是 visit(FileSystemNode)，编译失败！
```

因此必须通过 `element.accept(visitor)` 间接调用，让 JVM 在**运行时**根据实际类型决定调用哪个 visit。

## 四、访问者模式的变体

### 4.1 基于反射的访问者（简化版）

使用 Java 反射可以在一定程度上简化访问者模式：

```java
public class ReflectiveVisitor {
    
    public void visit(Object obj, Visitor visitor) {
        // 通过反射获取实际类型
        String methodName = "visit" + obj.getClass().getSimpleName();
        try {
            Method method = visitor.getClass().getMethod(methodName, obj.getClass());
            method.invoke(visitor, obj);
        } catch (NoSuchMethodException e) {
            // 尝试父类型
            for (Class<?> iface : obj.getClass().getInterfaces()) {
                try {
                    Method method = visitor.getClass().getMethod(methodName, iface);
                    method.invoke(visitor, obj);
                    return;
                } catch (NoSuchMethodException ignored) {}
            }
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
    
    public interface Visitor {
        default void visitFile(File file) {}
        default void visitFolder(Folder folder) {}
    }
}
```

### 4.2 带回执的访问者

有时候访问者需要返回结果给客户端：

```java
// 访问者带返回值
public interface VisitorWithResult<R> {
    R visitFile(File file);
    R visitFolder(Folder folder);
}

// 使用示例：计算总大小
public class SizeCalculator<R> implements VisitorWithResult<Long> {
    @Override
    public Long visitFile(File file) {
        return file.getSize();
    }
    
    @Override
    public Long visitFolder(Folder folder) {
        return folder.getChildren().stream()
            .mapToLong(child -> child.accept(new SizeCalculator<>()))
            .sum();
    }
}
```

### 4.3 组合访问者

组合多个访问者，一次遍历执行多种操作：

```java
public class CompositeVisitor implements FileSystemVisitor {
    private final List<FileSystemVisitor> visitors = new ArrayList<>();
    
    public void add(FileSystemVisitor visitor) {
        visitors.add(visitor);
    }
    
    @Override
    public void visit(File file) {
        visitors.forEach(v -> v.visit(file));
    }
    
    @Override
    public void visit(Folder folder) {
        for (FileSystemNode child : folder.getChildren()) {
            child.accept(this);
        }
        visitors.forEach(v -> v.visit(folder));
    }
}

// 使用
CompositeVisitor composite = new CompositeVisitor();
composite.add(new SizeCalculatorVisitor());
composite.add(new FileSearchVisitor("test"));
composite.add(new PrintStructureVisitor());
root.accept(composite);
```

## 五、访问者模式在 JDK 中的应用

### 5.1 NIO FileVisitor

JDK 的 `java.nio.file.FileVisitor` 是访问者模式的经典应用：

```java
public interface FileVisitor<T> {
    // 在访问文件之前调用
    default FileVisitResult preVisitDirectory(T dir, BasicFileAttributes attrs) 
        throws IOException { return FileVisitResult.CONTINUE; }
    
    // 访问文件时调用
    default FileVisitResult visitFile(T file, BasicFileAttributes attrs) 
        throws IOException { return FileVisitResult.CONTINUE; }
    
    // 访问文件失败时调用
    default FileVisitResult visitFileFailed(T file, IOException exc) 
        throws IOException { return FileVisitResult.CONTINUE; }
    
    // 在访问目录之后调用
    default FileVisitResult postVisitDirectory(T dir, IOException exc) 
        throws IOException { return FileVisitResult.CONTINUE; }
}

// 使用示例：递归删除目录
public class DeleteFileVisitor implements FileVisitor<Path> {
    @Override
    public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
        return FileVisitResult.CONTINUE;
    }
    
    @Override
    public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
        try {
            Files.delete(file);
            System.out.println("已删除文件: " + file);
        } catch (IOException e) {
            System.err.println("删除失败: " + file);
        }
        return FileVisitResult.CONTINUE;
    }
    
    @Override
    public FileVisitResult postVisitDirectory(Path dir, IOException exc) {
        try {
            Files.delete(dir);
            System.out.println("已删除目录: " + dir);
        } catch (IOException e) {
            System.err.println("删除失败: " + dir);
        }
        return FileVisitResult.CONTINUE;
    }
    
    @Override
    public FileVisitResult visitFileFailed(Path file, IOException exc) {
        System.err.println("访问失败: " + file + " - " + exc.getMessage());
        return FileVisitResult.CONTINUE;
    }
}

// 使用
Path start = Paths.get("/tmp/test");
Files.walkFileTree(start, new DeleteFileVisitor());
```

### 5.2 DOM Level 2 NodeVisitor

XML DOM 中的 `Node` 类也体现了访问者思想：

```java
// javax.xml.parsers.DocumentBuilder 解析后返回 Document
// 类似访问者的遍历方式
public void printDOM(Node node, int level) {
    String indent = "  ".repeat(level);
    System.out.println(indent + node.getNodeName() + ": " + node.getNodeValue());
    
    NodeList children = node.getChildNodes();
    for (int i = 0; i < children.getLength(); i++) {
        printDOM(children.item(i), level + 1);
    }
}
```

### 5.3 JavaCompiler AST Visitor

JDK 内部的 JavaCompiler 使用访问者模式遍历抽象语法树：

```java
// javax.lang.model.element.Element 和 javax.lang.model.type.TypeMirror
// 使用 accept 方法
public interface ElementVisitor<R, P> {
    R visit(Element e, P p);
    R visitAnnotation Miranda(Element e, P p);
    R visitError(DiagnosticKind kind, Element e, P p);
    // ... 其他 visit 方法
}

// Element 接口
public interface Element extends AnnotatedConstruct {
    <R, P> R accept(ElementVisitor<R, P> v, P p);
}
```

### 5.4 javax.lang.model 类型访问

```java
// TypeVisitor 用于访问类型层次结构
public interface TypeVisitor<D, R> {
    R visit(TypeMirror t, D d);
    R visitArrayType(ArrayType t, D d);
    R visitDeclaredType(DeclaredType t, D d);
    R visitErrorType(ErrorType t, D d);
    R visitExecutableType(ExecutableType t, D d);
    R visitNullType(NullType t, D d);
    R visitPrimitiveType(PrimitiveType t, D d);
    R visitTypeVariable(TypeVariable t, D d);
    R visitWildcardType(WildcardType t, D d);
}
```

## 六、访问者模式 vs 其他模式

### 6.1 对比策略模式

| 维度 | 访问者模式 | 策略模式 |
|------|-----------|---------|
| 目的 | 对多种异构元素执行操作 | 选择算法/策略 |
| 分发 | 双重分发（元素+访问者） | 单重分发（上下文选择） |
| 扩展性 | 新增操作容易，新增元素难 | 新增策略容易 |
| 元素关系 | 元素类稳定，操作常变 | 策略类稳定，上下文稳定 |

```java
// 策略模式：算法独立， Context 持有 Strategy
Strategy s = new QuickSort();
context.setStrategy(s);
context.execute();

// 访问者模式：操作作用于异构元素集合
root.accept(new SizeCalculatorVisitor());
root.accept(new SearchVisitor("keyword"));
```

### 6.2 对比组合模式

访问者模式经常与组合模式联用：

- **组合模式**：提供统一的元素接口，构建树形结构
- **访问者模式**：对树形结构执行各种操作

```java
// 组合 + 访问者
Folder root = new Folder("root");
root.add(new File("a.txt", 100));
root.add(new Folder("sub").add(new File("b.txt", 200)));

// 访问者操作组合结构
root.accept(new SizeCalculatorVisitor());
```

### 6.3 对比迭代器模式

| 维度 | 访问者模式 | 迭代器模式 |
|------|-----------|-----------|
| 关注点 | 对每个元素执行操作 | 顺序访问元素 |
| 遍历控制 | 访问者控制遍历逻辑 | 迭代器控制遍历 |
| 返回值 | 可以返回结果 | 通常无返回值 |

## 七、访问者模式的优缺点

### 优点

1. **开闭原则**：新增操作无需修改元素类
2. **单一职责**：每个访问者只负责一种操作
3. **复用性**：同一元素可被不同访问者复用
4. **灵活组合**：可以组合多个访问者一次遍历

### 缺点

1. **复杂性高**：双重分发增加了理解难度
2. **增加新元素困难**：需要修改所有访问者
3. **破坏封装**：访问者需要了解元素的内部结构
4. **类型安全**：依赖编译器的重载解析

### 适用场景

- 对象结构稳定，但需要经常定义新操作
- 需要对一个对象结构中的元素执行多种不相关的操作
- 编译器、AST 解析器、文件浏览器等结构固定的场景

## 八、实战：SQL 语句构建器

用访问者模式构建类型安全的 SQL 语句：

```java
// ========== 元素定义 ==========
public abstract class SqlNode {
    public abstract void accept(SqlVisitor visitor);
    public abstract String toSql();
}

public class SelectClause extends SqlNode {
    private final List<String> columns = new ArrayList<>();
    private final List<String> tables = new ArrayList<>();
    
    public SelectClause select(String... cols) {
        this.columns.addAll(Arrays.asList(cols));
        return this;
    }
    
    public SelectClause from(String table) {
        this.tables.add(table);
        return this;
    }
    
    public List<String> getColumns() { return columns; }
    public List<String> getTables() { return tables; }
    
    @Override
    public void accept(SqlVisitor visitor) { visitor.visit(this); }
    
    @Override
    public String toSql() {
        return "SELECT " + String.join(", ", columns) + 
               " FROM " + String.join(", ", tables);
    }
}

public class WhereClause extends SqlNode {
    private String condition;
    
    public WhereClause(String condition) {
        this.condition = condition;
    }
    
    public String getCondition() { return condition; }
    
    @Override
    public void accept(SqlVisitor visitor) { visitor.visit(this); }
    
    @Override
    public String toSql() {
        return " WHERE " + condition;
    }
}

public class OrderByClause extends SqlNode {
    private final List<String> orders = new ArrayList<>();
    
    public OrderByClause orderBy(String... cols) {
        this.orders.addAll(Arrays.asList(cols));
        return this;
    }
    
    public List<String> getOrders() { return orders; }
    
    @Override
    public void accept(SqlVisitor visitor) { visitor.visit(this); }
    
    @Override
    public String toSql() {
        return " ORDER BY " + String.join(", ", orders);
    }
}

// ========== 访问者 ==========
public interface SqlVisitor {
    void visit(SelectClause select);
    void visit(WhereClause where);
    void visit(OrderByClause orderBy);
}

// 验证访问者
public class SqlValidateVisitor implements SqlVisitor {
    private final List<String> errors = new ArrayList<>();
    
    @Override
    public void visit(SelectClause select) {
        if (select.getColumns().isEmpty()) {
            errors.add("SELECT 子句不能为空");
        }
        if (select.getTables().isEmpty()) {
            errors.add("FROM 子句不能为空");
        }
    }
    
    @Override
    public void visit(WhereClause where) {
        if (where.getCondition() == null || where.getCondition().isEmpty()) {
            errors.add("WHERE 条件不能为空");
        }
    }
    
    @Override
    public void visit(OrderByClause orderBy) {
        // ORDER BY 无需验证
    }
    
    public boolean isValid() { return errors.isEmpty(); }
    public List<String> getErrors() { return errors; }
}

// SQL 构建器
public class SqlBuilder {
    private final List<SqlNode> clauses = new ArrayList<>();
    
    public SqlBuilder select(String... cols) {
        SelectClause select = new SelectClause();
        select.select(cols);
        clauses.add(select);
        return this;
    }
    
    public SqlBuilder from(String table) {
        // 合并到已有的 SelectClause
        ((SelectClause) clauses.get(0)).from(table);
        return this;
    }
    
    public SqlBuilder where(String condition) {
        clauses.add(new WhereClause(condition));
        return this;
    }
    
    public SqlBuilder orderBy(String... cols) {
        clauses.add(new OrderByClause().orderBy(cols));
        return this;
    }
    
    // 使用访问者验证
    public boolean validate() {
        SqlValidateVisitor validator = new SqlValidateVisitor();
        for (SqlNode clause : clauses) {
            clause.accept(validator);
        }
        return validator.isValid();
    }
    
    public String build() {
        StringBuilder sb = new StringBuilder();
        for (SqlNode clause : clauses) {
            sb.append(clause.toSql());
        }
        return sb.toString();
    }
}

// 使用
public class SqlBuilderDemo {
    public static void main(String[] args) {
        String sql = new SqlBuilder()
            .select("id", "name", "age")
            .from("users")
            .where("age > 18 AND status = 'active'")
            .orderBy("id DESC", "name ASC")
            .build();
        
        System.out.println(sql);
        // 输出: SELECT id, name, age FROM users WHERE age > 18 AND status = 'active' ORDER BY id DESC, name ASC
    }
}
```

## 九、访问者模式在 Spring 中的应用

### 9.1 BeanDefinitionVisitor

Spring 使用访问者模式遍历 BeanDefinition：

```java
// Spring 源码：BeanDefinitionVisitor
public class BeanDefinitionVisitor {
    
    @Nullable
    private StringPlaceholderResolver placeholderResolver;
    
    public BeanDefinitionVisitor(StringPlaceholderResolver placeholderResolver) {
        this.placeholderResolver = placeholderResolver;
    }
    
    // visitXXX 方法遍历 BeanDefinition 的各个属性
    protected void visitBeanDefinition(BeanDefinitionHolder bdHolder) {
        visitBeanDefinitionName(bdHolder.getBeanName());
        visitBeanDefinitionClassName(bdHolder.getBeanDefinition());
        visitScope(bdHolder.getScope());
        visitPropertyValues(bdHolder.getBeanDefinition().getPropertyValues());
        // ...
    }
    
    protected void visitBeanDefinitionClassName(BeanDefinition bd) {
        String className = bd.getBeanClassName();
        if (className != null) {
            bd.setBeanClassName(resolveStringValue(className));
        }
    }
}
```

### 9.2 BeanWrapper 的访问

```java
// org.springframework.beans.PropertyAccessor
// 支持以访问者模式访问 Bean 的属性
public interface PropertyAccessor {
    // 类似访问者的遍历
    boolean isReadableProperty(String propertyName);
    boolean isWritableProperty(String propertyName);
    Class<?> getPropertyType(String propertyName) throws BeansException;
    @Nullable
    Object getPropertyValue(String propertyName) throws BeansException;
    void setPropertyValue(String propertyName, Object value) throws BeansException;
}
```

## 十、访问者模式与函数式编程

### 10.1 使用 Lambda 简化

Java 8 之后，可以用函数式接口简化访问者：

```java
// 函数式访问者
@FunctionalInterface
public interface ElementVisitor<T, R> {
    R visit(T element);
}

// 文件系统节点
public abstract class FsNode {
    public abstract <R> R accept(Function<File, R> fileHandler,
                                   Function<Folder, R> folderHandler);
}

public class FFile extends FsNode {
    private final String name;
    private final long size;
    
    public FFile(String name, long size) {
        this.name = name;
        this.size = size;
    }
    
    @Override
    public <R> R accept(Function<File, R> fileHandler,
                         Function<Folder, R> folderHandler) {
        return fileHandler.apply(this);
    }
    
    public String getName() { return name; }
    public long getSize() { return size; }
}

public class FFolder extends FsNode {
    private final String name;
    private final List<FsNode> children = new ArrayList<>();
    
    public FFolder(String name) {
        this.name = name;
    }
    
    public void add(FsNode node) { children.add(node); }
    
    @Override
    public <R> R accept(Function<File, R> fileHandler,
                         Function<Folder, R> folderHandler) {
        return folderHandler.apply(this);
    }
    
    public String getName() { return name; }
    public List<FsNode> getChildren() { return children; }
}

// 使用 Lambda
long totalSize = 0;
for (FsNode node : allNodes) {
    node.accept(
        file -> { totalSize += file.getSize(); return null; },  // File handler
        folder -> { folder.getChildren().forEach(c -> c.accept(...)); return null; } // Folder handler
    );
}
```

### 10.2 Visitor 模式与巡检（Traversable）接口

```java
// 引入巡检接口，结合访问者和函数式
public interface Traversable<T> {
    void traverse(Consumer<T> action);
    <R> R accept(Function<T, R> visitor);
}

// 使用
List<Traversable<Node>> nodes = getNodes();
nodes.forEach(n -> n.traverse(node -> {
    if (node instanceof File) processFile((File) node);
    else if (node instanceof Folder) processFolder((Folder) node);
}));
```

## 十一、面试常见问题

### Q1: 访问者模式的核心思想是什么？

访问者模式通过**双重分发**机制，将数据结构与作用于数据上的操作解耦。元素的 `accept` 方法决定调用访问者的哪个 `visit` 方法，访问者的 `visit` 方法实现具体操作。这样新增操作时无需修改元素类，符合开闭原则。

### Q2: 为什么需要双重分发？一次分发不够吗？

Java 是静态类型语言，方法重载在编译时根据参数声明类型决定。如果直接 `visitor.visit(element)`，编译器只能选择 `visit(FileSystemNode)` 而非 `visit(File)`。通过 `element.accept(visitor)`，让元素的运行时类型决定调用哪个 visit 方法，实现真正的多态。

### Q3: 访问者模式的缺点是什么？

最大的缺点是**增加新元素类困难**。每新增一种元素，都需要修改所有访问者的 `visit` 方法。因此访问者模式适用于数据结构稳定、操作经常变化的场景（如编译器 AST、文件系统遍历）。

### Q4: 访问者模式和策略模式有什么区别？

策略模式关注的是**算法的选择**，一个上下文持有一种策略，运行时可以替换策略。访问者模式关注的是**对异构对象的操作**，一个对象结构可以被多种访问者以不同方式遍历。

### Q5: 什么场景下应该使用访问者模式？

- 对象结构相对稳定，但需要经常定义新操作
- 需要对一个对象结构中的元素执行多种不相关操作
- 需要在遍历过程中积累状态（如统计、收集）
- 编译器、解析器、文件浏览器、报表生成器等固定结构的场景

### Q6: 如何在访问者模式中返回结果？

可以定义带回执的访问者接口，或使用访问者返回结果对象。也可以在访问者内部维护状态，通过 getter 方法获取结果。

### Q7: 访问者模式如何保证类型安全？

通过泛型和编译时类型检查保证。对于 `visit(ElementA)` 和 `visit(ElementB)` 两个重载方法，编译器会根据参数静态类型选择，但如果使用不当可能产生意外结果。最佳实践是在 `Element.accept()` 中强制类型转换。

## 十二、总结

访问者模式是设计模式中最"重"的一个，它的出现是为了解决一个核心矛盾：**数据结构相对稳定，但操作经常变化**。

**核心要点**：

1. **双重分发**：通过 `element.accept(visitor)` + `visitor.visit(element)` 实现
2. **开闭原则**：新增操作不修改元素，新增元素修改操作
3. **适用场景**：AST、文件系统、XML/HTML DOM、报表生成
4. **JDK 应用**：FileVisitor、JavaCompiler ElementVisitor、BeanDefinitionVisitor

访问者模式虽然复杂，但在合适的场景下能带来极好的扩展性。理解它，你对 Java 多态和类型系统的理解也会更上一层楼。

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
