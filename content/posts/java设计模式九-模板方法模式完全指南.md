---
title: "Java设计模式（九）：模板方法模式完全指南"
date: 2026-04-20T11:10:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "模板方法", "template method"]
---

## 前言

前八篇文章我们介绍了创建型模式和多种行为型模式。今天继续 Java 设计模式系列，**模板方法模式（Template Method Pattern）** 是结构化流程的利器，完美体现了"复用"和"扩展"的平衡。

**核心思想**：定义一个算法的骨架，将某些步骤延迟到子类中实现。模板方法使得子类可以在不改变算法结构的情况下，重新定义算法的某些特定步骤。

<!--more-->

## 一、为什么需要模板方法模式

### 1.1 重复代码的噩梦

```java
// ❌ 典型重复代码：数据导出功能
public class ExcelExporter {
    
    public void export(String data) {
        // 1. 连接数据源
        connect();
        
        // 2. 查询数据
        List<String> dataList = queryData(data);
        
        // 3. 数据转换
        List<String[]> formatted = formatData(dataList);
        
        // 4. 生成 Excel
        byte[] excel = generateExcel(formatted);
        
        // 5. 写入文件
        writeFile(excel, data + ".xlsx");
        
        // 6. 发送通知
        sendNotification("导出完成");
        
        // 7. 记录日志
        log("导出成功");
    }
}

public class CsvExporter {
    
    public void export(String data) {
        // 1. 连接数据源
        connect();
        
        // 2. 查询数据
        List<String> dataList = queryData(data);
        
        // 3. 数据转换
        List<String[]> formatted = formatData(dataList);
        
        // 4. 生成 CSV（不同）
        byte[] csv = generateCsv(formatted);
        
        // 5. 写入文件
        writeFile(csv, data + ".csv");
        
        // 6. 发送通知（相同）
        sendNotification("导出完成");
        
        // 7. 记录日志（相同）
        log("导出成功");
    }
}

public class PdfExporter {
    
    public void export(String data) {
        // 1. 连接数据源
        connect();
        
        // 2. 查询数据
        List<String> dataList = queryData(data);
        
        // 3. 数据转换
        List<String[]> formatted = formatData(dataList);
        
        // 4. 生成 PDF（不同）
        byte[] pdf = generatePdf(formatted);
        
        // 5. 写入文件
        writeFile(pdf, data + ".pdf");
        
        // 6. 发送通知（相同）
        sendNotification("导出完成");
        
        // 7. 记录日志（相同）
        log("导出成功");
    }
}
```

**问题**：
- 大量重复代码：connect、queryData、sendNotification、log 几乎一样
- 违反 DRY 原则：Don't Repeat Yourself
- 维护困难：修改一个步骤需要改多处
- 扩展困难：新增导出格式需要复制整个流程

### 1.2 模板方法模式的优势

```java
// ✅ 使用模板方法模式
public abstract class AbstractExporter {
    
    // 模板方法：定义算法骨架
    public final void export(String data) {
        connect();              // 步骤1：连接（可重写）
        List<String> dataList = queryData(data);  // 步骤2：查询
        List<String[]> formatted = formatData(dataList);  // 步骤3：格式化
        byte[] file = doGenerate(formatted);      // 步骤4：生成（子类实现）
        String filename = getFileName(data);      // 步骤5：文件名
        writeFile(file, filename);                // 步骤6：写入
        sendNotification("导出完成");             // 步骤7：通知
        log("导出成功");                          // 步骤8：日志
    }
    
    // 公共方法（可复用）
    protected void connect() { /* 通用连接逻辑 */ }
    protected void sendNotification(String msg) { /* 通用通知 */ }
    protected void log(String msg) { /* 通用日志 */ }
    
    // 抽象方法（子类必须实现）
    protected abstract List<String[]> formatData(List<String> dataList);
    protected abstract byte[] doGenerate(List<String[]> data);
    protected abstract String getFileName(String data);
    
    // 钩子方法（可选重写）
    protected void queryData(String data) {
        // 默认实现
    }
}
```

**优点**：
- 复用公共流程
- 扩展可变步骤
- 符合开闭原则
- 代码结构清晰

## 二、模板方法模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│           AbstractClass (抽象模板类)                          │
├─────────────────────────────────────────────────────────────┤
│ + templateMethod()           ← 模板方法（final）              │
│ # step1()                   ← 具体公共步骤                    │
│ # step2()                   ← 可重写步骤（默认实现）           │
│ # abstract step3()          ← 抽象步骤（子类实现）            │
│ # hook()                    ← 钩子方法（可选重写）            │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴────────────────┐
▼                             ▼
┌─────────────────┐  ┌─────────────────┐
│ ConcreteClassA  │  │ ConcreteClassB  │
├─────────────────┤  ├─────────────────┤
│ + step3() {...} │  │ + step3() {...} │
│ + hook() {...}  │  │                 │
└─────────────────┘  └─────────────────┘
```

### 2.2 完整代码实现

```java
// 抽象模板类
public abstract class Abstract CaffeineBeverage {
    
    // 模板方法：final 防止被子类重写
    public final void prepareRecipe() {
        boilWater();           // 步骤1：烧水
        brew();                // 步骤2：冲泡
        pourInCup();           // 步骤3：倒入杯中
        addCondiments();       // 步骤4：添加调料
    }
    
    // 公共方法（子类共用）
    protected void boilWater() {
        System.out.println("烧水...");
    }
    
    protected void pourInCup() {
        System.out.println("倒入杯中...");
    }
    
    // 抽象方法（子类必须实现）
    protected abstract void brew();
    protected abstract void addCondiments();
}

// 具体模板：茶
public class Tea extends CaffeineBeverage {
    
    @Override
    protected void brew() {
        System.out.println("冲泡茶叶...");
    }
    
    @Override
    protected void addCondiments() {
        System.out.println("添加柠檬...");
    }
}

// 具体模板：咖啡
public class Coffee extends CaffeineBeverage {
    
    @Override
    protected void brew() {
        System.out.println("冲泡咖啡粉...");
    }
    
    @Override
    protected void addCondiments() {
        System.out.println("添加糖和牛奶...");
    }
}

// 测试
public class TemplateMethodTest {
    public static void main(String[] args) {
        System.out.println("=== 泡茶 ===");
        CaffeineBeverage tea = new Tea();
        tea.prepareRecipe();
        
        System.out.println("\n=== 泡咖啡 ===");
        CaffeineBeverage coffee = new Coffee();
        coffee.prepareRecipe();
    }
}
```

**输出**：
```
=== 泡茶 ===
烧水...
冲泡茶叶...
倒入杯中...
添加柠檬...

=== 泡咖啡 ===
烧水...
冲泡咖啡粉...
倒入杯中...
添加糖和牛奶...
```

## 三、钩子方法（Hook）

### 3.1 什么是钩子方法

钩子方法是模板方法中的可选方法，提供默认实现，子类可以选择性地重写它。钩子用于：
- 提供默认实现（可选覆盖）
- 控制算法的某些部分
- 条件判断

### 3.2 带钩子的咖啡

```java
// 带钩子的抽象类
public abstract class CaffeineBeverageWithHook {
    
    public final void prepareRecipe() {
        boilWater();
        brew();
        pourInCup();
        
        // 钩子方法：决定是否添加调料
        if (customerWantsCondiments()) {
            addCondiments();
        }
    }
    
    protected void boilWater() {
        System.out.println("烧水...");
    }
    
    protected void pourInCup() {
        System.out.println("倒入杯中...");
    }
    
    protected abstract void brew();
    protected abstract void addCondiments();
    
    // 钩子方法：默认返回 true
    protected boolean customerWantsCondiments() {
        return true;
    }
}

// 咖啡（带钩子）
public class CoffeeWithHook extends CaffeineBeverageWithHook {
    
    @Override
    protected void brew() {
        System.out.println("冲泡咖啡粉...");
    }
    
    @Override
    protected void addCondiments() {
        System.out.println("添加糖和牛奶...");
    }
    
    // 重写钩子方法
    @Override
    protected boolean customerWantsCondiments() {
        String answer = getUserInput();
        return answer.toLowerCase().startsWith("y");
    }
    
    private String getUserInput() {
        // 模拟用户输入
        return "no";  // 用户选择不加调料
    }
}
```

### 3.3 钩子的应用场景

```java
// 场景1：日志钩子
public abstract class DataProcessor {
    
    public final void process() {
        // 前置处理
        beforeProcess();
        
        // 核心处理
        doProcess();
        
        // 后置处理
        afterProcess();
        
        // 日志钩子
        if (shouldLog()) {
            log();
        }
    }
    
    // 钩子：默认记录日志
    protected boolean shouldLog() {
        return true;
    }
    
    protected void beforeProcess() { /* ... */ }
    protected void afterProcess() { /* ... */ }
    protected void log() { System.out.println("处理完成"); }
    
    protected abstract void doProcess();
}

// 场景2：验证钩子
public abstract class Validator {
    
    public final boolean validate(Object data) {
        // 前置验证
        if (!preValidate(data)) {
            return false;
        }
        
        // 核心验证
        if (!doValidate(data)) {
            return false;
        }
        
        // 后置验证
        return postValidate(data);
    }
    
    // 钩子：前置验证
    protected boolean preValidate(Object data) {
        return data != null;  // 默认非空检查
    }
    
    // 钩子：后置验证
    protected boolean postValidate(Object data) {
        return true;  // 默认直接通过
    }
    
    protected abstract boolean doValidate(Object data);
}
```

## 四、实战案例

### 4.1 数据导出系统

```java
// 导出模板抽象类
public abstract class AbstractExporter {
    
    // 模板方法：final 防止重写
    public final void export(String data) {
        // 1. 连接数据源
        connect();
        
        // 2. 查询数据
        List<String> rawData = queryData(data);
        
        // 3. 数据转换
        List<String[]> formatted = transform(rawData);
        
        // 4. 生成文件
        byte[] fileContent = doGenerate(formatted);
        
        // 5. 写入文件
        String fileName = getFileName(data);
        writeFile(fileContent, fileName);
        
        // 6. 发送通知
        sendNotification("导出成功");
        
        // 7. 记录日志
        log("导出完成");
    }
    
    // 公共方法
    protected void connect() {
        System.out.println("连接数据库...");
    }
    
    protected List<String> queryData(String data) {
        System.out.println("查询数据: " + data);
        return Arrays.asList("row1", "row2", "row3");
    }
    
    protected void sendNotification(String message) {
        System.out.println("发送通知: " + message);
    }
    
    protected void log(String message) {
        System.out.println("[LOG] " + message);
    }
    
    protected void writeFile(byte[] content, String fileName) {
        System.out.println("写入文件: " + fileName);
    }
    
    // 抽象方法（子类必须实现）
    protected abstract List<String[]> transform(List<String> rawData);
    protected abstract byte[] doGenerate(List<String[]> data);
    protected abstract String getFileName(String data);
}

// Excel 导出
public class ExcelExporter extends AbstractExporter {
    
    @Override
    protected List<String[]> transform(List<String> rawData) {
        System.out.println("转换为 Excel 格式...");
        return rawData.stream()
            .map(s -> new String[]{s, "col2", "col3"})
            .collect(Collectors.toList());
    }
    
    @Override
    protected byte[] doGenerate(List<String[]> data) {
        System.out.println("生成 Excel 文件...");
        return "模拟 Excel 内容".getBytes();
    }
    
    @Override
    protected String getFileName(String data) {
        return data + ".xlsx";
    }
}

// CSV 导出
public class CsvExporter extends AbstractExporter {
    
    @Override
    protected List<String[]> transform(List<String> rawData) {
        System.out.println("转换为 CSV 格式...");
        return rawData.stream()
            .map(s -> s.split(","))
            .collect(Collectors.toList());
    }
    
    @Override
    protected byte[] doGenerate(List<String[]> data) {
        System.out.println("生成 CSV 文件...");
        StringBuilder sb = new StringBuilder();
        for (String[] row : data) {
            sb.append(String.join(",", row)).append("\n");
        }
        return sb.toString().getBytes();
    }
    
    @Override
    protected String getFileName(String data) {
        return data + ".csv";
    }
}

// PDF 导出
public class PdfExporter extends AbstractExporter {
    
    @Override
    protected List<String[]> transform(List<String> rawData) {
        System.out.println("转换为 PDF 格式...");
        return rawData.stream()
            .map(s -> new String[]{s})
            .collect(Collectors.toList());
    }
    
    @Override
    protected byte[] doGenerate(List<String[]> data) {
        System.out.println("生成 PDF 文件...");
        return "模拟 PDF 内容".getBytes();
    }
    
    @Override
    protected String getFileName(String data) {
        return data + ".pdf";
    }
}

// JSON 导出
public class JsonExporter extends AbstractExporter {
    
    // 钩子：JSON 导出不需要 queryData
    @Override
    protected List<String> queryData(String data) {
        System.out.println("查询 JSON 数据...");
        return Arrays.asList("{\"id\":1}", "{\"id\":2}");
    }
    
    @Override
    protected List<String[]> transform(List<String> rawData) {
        System.out.println("转换为 JSON 格式...");
        return rawData.stream()
            .map(s -> new String[]{s})
            .collect(Collectors.toList());
    }
    
    @Override
    protected byte[] doGenerate(List<String[]> data) {
        System.out.println("生成 JSON 文件...");
        String json = "[" + String.join(",", 
            Arrays.stream(data).flatMap(Arrays::stream).toArray(String[]::new)) + "]";
        return json.getBytes();
    }
    
    @Override
    protected String getFileName(String data) {
        return data + ".json";
    }
}

// 测试
public class ExporterTest {
    public static void main(String[] args) {
        System.out.println("=== 导出 Excel ===");
        AbstractExporter excel = new ExcelExporter();
        excel.export("report");
        
        System.out.println("\n=== 导出 CSV ===");
        AbstractExporter csv = new CsvExporter();
        csv.export("report");
    }
}
```

### 4.2 测试框架

```java
// 测试模板
public abstract class AbstractTest {
    
    // 模板方法
    public final void run() {
        // 1. 前置准备
        beforeAll();
        
        // 2. 每个测试前
        setUp();
        
        // 3. 执行测试
        try {
            test();
            
            // 4. 记录结果
            onSuccess();
        } catch (Exception e) {
            onFailure(e);
        }
        
        // 5. 每个测试后清理
        tearDown();
        
        // 6. 后置清理
        afterAll();
    }
    
    protected void beforeAll() {
        System.out.println("测试开始...");
    }
    
    protected void afterAll() {
        System.out.println("测试结束...");
    }
    
    protected abstract void setUp();
    protected abstract void test() throws Exception;
    protected abstract void tearDown();
    
    protected void onSuccess() {
        System.out.println("  ✅ 测试通过");
    }
    
    protected void onFailure(Exception e) {
        System.out.println("  ❌ 测试失败: " + e.getMessage());
    }
}

// 具体测试
public class CalculatorTest extends AbstractTest {
    
    private Calculator calculator;
    
    @Override
    protected void setUp() {
        System.out.println("  创建计算器实例...");
        calculator = new Calculator();
    }
    
    @Override
    protected void test() throws Exception {
        // 测试加法
        int result = calculator.add(1, 2);
        if (result != 3) {
            throw new AssertionError("期望 3，实际 " + result);
        }
        
        // 测试乘法
        result = calculator.multiply(3, 4);
        if (result != 12) {
            throw new AssertionError("期望 12，实际 " + result);
        }
    }
    
    @Override
    protected void tearDown() {
        System.out.println("  清理测试数据...");
    }
}

// 计算器
class Calculator {
    int add(int a, int b) { return a + b; }
    int multiply(int a, int b) { return a * b; }
}
```

### 4.3 支付处理流程

```java
// 支付模板
public abstract class AbstractPaymentProcessor {
    
    // 模板方法
    public final PaymentResult process(Order order) {
        // 1. 验证订单
        if (!validateOrder(order)) {
            return PaymentResult.fail("订单验证失败");
        }
        
        // 2. 扣款前检查
        if (!beforeDeduct(order)) {
            return PaymentResult.fail("扣款前检查失败");
        }
        
        // 3. 执行扣款
        PaymentResult result = doPay(order);
        
        // 4. 扣款后处理
        afterPay(order, result);
        
        // 5. 发送结果通知
        notifyResult(order, result);
        
        return result;
    }
    
    // 公共验证
    protected boolean validateOrder(Order order) {
        if (order == null) return false;
        if (order.getAmount() <= 0) return false;
        return true;
    }
    
    // 钩子：扣款前检查（可选重写）
    protected boolean beforeDeduct(Order order) {
        return true;  // 默认直接通过
    }
    
    // 抽象方法：扣款逻辑
    protected abstract PaymentResult doPay(Order order);
    
    // 钩子：扣款后处理（可选重写）
    protected void afterPay(Order order, PaymentResult result) {
        // 默认实现：记录日志
        System.out.println("记录支付日志...");
    }
    
    protected void notifyResult(Order order, PaymentResult result) {
        System.out.println("通知用户支付" + (result.isSuccess() ? "成功" : "失败"));
    }
}

// 支付宝支付
public class AlipayProcessor extends AbstractPaymentProcessor {
    
    @Override
    protected PaymentResult doPay(Order order) {
        System.out.println("调用支付宝 SDK...");
        // 调用支付宝接口
        return PaymentResult.success("支付宝_" + order.getOrderId());
    }
}

// 微信支付
public class WechatPayProcessor extends AbstractPaymentProcessor {
    
    @Override
    protected boolean beforeDeduct(Order order) {
        // 微信特殊检查：风控验证
        System.out.println("微信风控检查...");
        return true;
    }
    
    @Override
    protected PaymentResult doPay(Order order) {
        System.out.println("调用微信支付 SDK...");
        return PaymentResult.success("微信_" + order.getOrderId());
    }
    
    @Override
    protected void afterPay(Order order, PaymentResult result) {
        super.afterPay(order, result);
        // 微信特殊：发送模板消息
        System.out.println("发送微信模板消息...");
    }
}

// 信用卡支付
public class CreditCardProcessor extends AbstractPaymentProcessor {
    
    @Override
    protected boolean beforeDeduct(Order order) {
        // 信用卡：检查额度
        System.out.println("检查信用卡额度...");
        return true;
    }
    
    @Override
    protected PaymentResult doPay(Order order) {
        System.out.println("调用信用卡支付网关...");
        return PaymentResult.success("信用卡_" + order.getOrderId());
    }
}

// 订单和结果类
class Order {
    String orderId;
    double amount;
    String getOrderId() { return orderId; }
    double getAmount() { return amount; }
}

class PaymentResult {
    private boolean success;
    private String message;
    
    static PaymentResult success(String msg) {
        PaymentResult r = new PaymentResult();
        r.success = true;
        r.message = msg;
        return r;
    }
    
    static PaymentResult fail(String msg) {
        PaymentResult r = new PaymentResult();
        r.success = false;
        r.message = msg;
        return r;
    }
    
    boolean isSuccess() { return success; }
    String getMessage() { return message; }
}
```

## 五、模板方法 vs 策略模式

### 5.1 对比

| 维度 | 模板方法 | 策略模式 |
|------|---------|---------|
| **目的** | 复用流程，扩展步骤 | 替换算法 |
| **实现方式** | 继承 | 组合 |
| **结构** | 抽象类定义骨架 | 接口定义行为 |
| **扩展方式** | 子类实现抽象方法 | 客户端选择策略 |
| **算法控制** | 模板控制 | 客户端控制 |
| **运行时** | 编译时确定 | 运行时可切换 |

### 5.2 选择指南

```java
// 选模板方法：当流程固定，步骤可变
// 例如：数据导出、测试框架、支付流程
public abstract class DataExporter {
    public final void export() {
        connect();      // 固定
        query();        // 可变
        transform();    // 可变
        write();        // 固定
        notify();       // 固定
    }
    // ...
}

// 选策略模式：当算法需要运行时切换
// 例如：排序算法、支付方式、压缩算法
public class Sorter {
    private SortStrategy strategy;
    
    public void sort(List<T> list) {
        strategy.sort(list);  // 运行时选择
    }
}
```

### 5.3 组合使用

```java
// 模板方法 + 策略模式
public abstract class AbstractPaymentProcessor {
    
    private NotificationStrategy notificationStrategy;
    
    public final void process(Order order) {
        // 固定流程
        validate(order);
        doPay(order);
        afterPay(order);
        
        // 策略模式：通知方式可选
        if (notificationStrategy != null) {
            notificationStrategy.notify(order);
        }
    }
    
    // 模板方法：扣款逻辑
    protected abstract void doPay(Order order);
}

// 通知策略
public interface NotificationStrategy {
    void notify(Order order);
}

public class EmailNotification implements NotificationStrategy {
    @Override
    public void notify(Order order) { /* 发送邮件 */ }
}

public class SmsNotification implements NotificationStrategy {
    @Override
    public void notify(Order order) { /* 发送短信 */ }
}
```

## 六、模板方法的优缺点

### 6.1 优点

1. **代码复用**：公共流程抽取到父类
2. **扩展性强**：新增子类只需实现抽象方法
3. **符合开闭原则**：不修改父类，扩展子类
4. **封装不变**：流程骨架封装在父类
5. **行为控制**：通过钩子方法控制行为

### 6.2 缺点

1. **继承限制**：只能通过继承实现
2. **类膨胀**：每种变体一个子类
3. **违反里氏替换**：子类可能改变父类期望的行为
4. **维护困难**：层级过深时难以理解

### 6.3 最佳实践

```java
// 1. 模板方法设为 final
public final void templateMethod() { /* ... */ }

// 2. 抽象方法明确标记
protected abstract void stepA();
protected abstract void stepB();

// 3. 钩子方法有默认实现
protected boolean shouldDoSomething() {
    return true;  // 默认执行
}

// 4. 最小化抽象方法数量
// 将多个相关步骤合并为一个抽象方法
protected abstract void performOperation();
```

## 七、源码中的应用

### 7.1 JDK - InputStream

```java
// JDK 中的模板方法模式
public abstract class InputStream implements Closeable {
    
    // 模板方法
    public int read(byte[] b, int off, int len) throws IOException {
        // 1. 检查参数
        if (b == null) {
            throw new NullPointerException();
        }
        
        // 2. 调用抽象方法读取
        int c = read();
        if (c == -1) {
            return -1;
        }
        
        // 3. 处理数据
        b[off] = (byte) c;
        int i = 1;
        try {
            for (; i < len; i++) {
                c = read();
                if (c == -1) {
                    break;
                }
                b[off + i] = (byte) c;
            }
        } catch (IOException ee) {
            // 处理异常
        }
        return i;
    }
    
    // 抽象方法：子类必须实现
    public abstract int read() throws IOException;
}

// FileInputStream
public class FileInputStream extends InputStream {
    @Override
    public int read() throws IOException {
        // 具体实现
    }
}

// ByteArrayInputStream
public class ByteArrayInputStream extends InputStream {
    @Override
    public int read() {
        // 具体实现
    }
}
```

### 7.2 JDK - AbstractList

```java
// 模板方法：addAll
public abstract class AbstractList<E> extends AbstractCollection<E> {
    
    public boolean addAll(int index, Collection<? extends E> c) {
        // 1. 验证位置
        rangeCheckForAdd(index);
        
        // 2. 转换为数组
        Object[] a = c.toArray();
        int numNew = a.length;
        
        // 3. 批量添加（模板方法）
        modCount++;
        
        // 4. 逐个插入（抽象方法）
        for (Object o : a) {
            add(index++, (E) o);
        }
        
        return numNew != 0;
    }
    
    // 抽象方法
    public abstract void add(int index, E element);
}

// 钩子方法
protected transient int modCount = 0;

protected void ensureCapacityInternal(int minCapacity) {
    // 钩子：可重写
    if (minCapacity - elementData.length > 0) {
        grow(minCapacity);
    }
}
```

### 7.3 Spring - JdbcTemplate

```java
// Spring 的 JdbcTemplate
public class JdbcTemplate {
    
    // 模板方法：query
    public <T> List<T> query(String sql, RowMapper<T> rowMapper) {
        // 1. 获取连接
        return execute(connection -> {
            // 2. 创建语句
            PreparedStatement ps = connection.prepareStatement(sql);
            
            // 3. 设置参数（钩子）
            doSetParameters(ps);
            
            // 4. 执行查询
            ResultSet rs = ps.executeQuery();
            
            // 5. 处理结果（策略）
            List<T> result = new ArrayList<>();
            int rowNum = 0;
            while (rs.next()) {
                result.add(rowMapper.mapRow(rs, rowNum++));
            }
            
            return result;
        });
    }
    
    // 钩子方法
    protected void doSetParameters(PreparedStatement ps) throws SQLException {
        // 默认空实现
    }
}
```

### 7.4 Spring - HibernateTemplate

```java
// Spring 的事务模板
public abstract class TransactionCallback<T> {
    // 回调接口
}

public class TransactionTemplate {
    
    public <T> T execute(TransactionCallback<T> action) {
        // 1. 开始事务
        begin();
        
        try {
            // 2. 执行回调
            return action.doInTransaction();
        } catch (Exception e) {
            // 3. 异常处理
            completeOnError(e);
            throw e;
        } finally {
            // 4. 最终处理
            cleanup();
        }
    }
}
```

## 八、面试常见问题

### Q1：模板方法和继承的区别？

| 维度 | 普通继承 | 模板方法 |
|------|---------|---------|
| 复用 | 不复用 | 复用流程骨架 |
| 扩展 | 重写全部方法 | 只重写必要方法 |
| 控制 | 子类完全控制 | 父类控制骨架 |

### Q2：模板方法和策略模式如何选择？

- **模板方法**：流程固定，步骤可变（继承）
- **策略模式**：算法可变，可运行时切换（组合）

### Q3：什么是钩子方法？有什么作用？

钩子方法是在抽象类中提供默认实现的方法，子类可以选择性地重写它。作用：
1. 提供默认实现（可选覆盖）
2. 控制算法的某些部分
3. 让子类有机会影响算法行为

### Q4：模板方法有什么缺点？如何优化？

**缺点**：
- 类数量增加
- 继承层次复杂

**优化**：
- 使用组合（策略模式）
- 合理使用钩子方法
- 控制继承层级

## 九、总结

### 模式对比

```
模板方法 vs 策略模式：
┌────────────┬────────────────────────────────┐
│   模式     │ 特点                            │
├────────────┼────────────────────────────────┤
│ 模板方法   │ 继承实现，父类控制骨架            │
│ 策略模式   │ 组合实现，客户端控制算法          │
├────────────┼────────────────────────────────┤
│ 共同点    │ 都是行为型模式                    │
│ 组合使用  │ 模板方法控制流程，策略控制细节     │
└────────────┴────────────────────────────────┘
```

### 核心要点

1. **模板方法**：final 防止重写
2. **抽象方法**：子类必须实现
3. **具体方法**：子类共用
4. **钩子方法**：可选重写

## 结语

模板方法模式是复用流程骨架的利器，特别适合有固定流程但步骤可变的场景。掌握模板方法，能够设计出更复用、更易扩展的系统。

**下期预告**：责任链模式（Chain of Responsibility Pattern）

> 记住：**模板方法是"骨架不变，步骤可变"**。
