---
title: "Java设计模式（十一）：命令模式完全解析"
date: 2026-04-20T13:15:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "命令模式", "command"]
---

## 前言

前九篇文章覆盖了多种创建型、结构型和行为型模式。今天继续 Java 设计模式系列，**命令模式（Command Pattern）** 是行为型模式中的经典，用于将请求封装为对象，实现请求的参数化、队列化、撤销/重做等功能。

**核心思想**：将请求封装为对象，从而可用不同的请求参数化客户；将请求排队或记录日志；支持可撤销的操作。

<!--more-->

## 一、为什么需要命令模式

### 1.1 紧耦合的请求处理

```java
// ❌ 典型问题：命令和处理者紧耦合
public class Button {
    
    public void click() {
        // 直接调用具体操作
        new LightOnCommand().execute();
    }
}

public class RemoteControl {
    
    public void press(int slot) {
        if (slot == 1) {
            light.on();
        } else if (slot == 2) {
            fan.high();
        } else if (slot == 3) {
            ac.cool(26);
        }
        // 每增加一个设备就要修改这里
    }
}
```

**问题**：
- 紧耦合：按钮必须知道具体操作
- 难以扩展：新增命令要改现有代码
- 难以撤销/重做：没有历史记录
- 难以日志/队列：请求无法持久化

### 1.2 命令模式的优势

```java
// ✅ 使用命令模式
public interface Command {
    void execute();
    void undo();  // 支持撤销
}

public class LightOnCommand implements Command {
    private Light light;
    
    public LightOnCommand(Light light) {
        this.light = light;
    }
    
    @Override
    public void execute() {
        light.on();
    }
    
    @Override
    public void undo() {
        light.off();
    }
}

// 遥控器不知道具体执行什么
public class RemoteControl {
    private Command[] commands;
    
    public void press(int slot) {
        commands[slot].execute();
    }
    
    public void undo() {
        commands[slot].undo();
    }
}
```

**优点**：
- 解耦发送者和接收者
- 支持撤销/重做
- 命令可排队、记录日志
- 新增命令无需改现有代码

## 二、命令模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                    Invoker (调用者)                          │
├─────────────────────────────────────────────────────────────┤
│ - command: Command                                         │
│ + setCommand(Command)                                     │
│ + executeCommand()                                          │
└─────────────────────────────────────────────────────────────┘
              │
              │ uses
              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Command (命令接口)                        │
├─────────────────────────────────────────────────────────────┤
│ + execute()                                               │
│ + undo()                                                  │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴──────────────────────────────┐
▼                                          ▼
┌─────────────────┐               ┌─────────────────┐
│ ConcreteCommand │───────────────│ ConcreteCommand │
├─────────────────┤               ├─────────────────┤
│ - receiver      │               │ - receiver      │
│ + execute()     │               │ + execute()     │
│ + undo()        │               │ + undo()        │
└─────────────────┘               └─────────────────┘
              │                             │
              └──────────────┬──────────────┘
                             │ calls
                             ▼
                    ┌─────────────────┐
                    │   Receiver      │
                    │ (实际执行者)     │
                    ├─────────────────┤
                    │ + action()      │
                    └─────────────────┘
```

### 2.2 完整代码实现

```java
// 命令接口
public interface Command {
    
    /**
     * 执行命令
     */
    void execute();
    
    /**
     * 撤销命令
     */
    void undo();
    
    /**
     * 重做命令
     */
    void redo();
}

// 接收者：电灯
public class Light {
    
    private String location;
    private boolean isOn = false;
    
    public Light(String location) {
        this.location = location;
    }
    
    public void on() {
        isOn = true;
        System.out.println(location + " 电灯打开");
    }
    
    public void off() {
        isOn = false;
        System.out.println(location + " 电灯关闭");
    }
    
    public boolean isOn() {
        return isOn;
    }
}

// 接收者：风扇
public class Fan {
    
    private String location;
    private int speed = 0;  // 0=关闭, 1=低速, 2=中速, 3=高速
    
    public Fan(String location) {
        this.location = location;
    }
    
    public void high() {
        speed = 3;
        System.out.println(location + " 风扇高速运转");
    }
    
    public void medium() {
        speed = 2;
        System.out.println(location + " 风扇中速运转");
    }
    
    public void low() {
        speed = 1;
        System.out.println(location + " 风扇低速运转");
    }
    
    public void off() {
        speed = 0;
        System.out.println(location + " 风扇关闭");
    }
    
    public int getSpeed() {
        return speed;
    }
}

// 具体命令：打开电灯
public class LightOnCommand implements Command {
    
    private Light light;
    private int previousState;  // 用于撤销
    
    public LightOnCommand(Light light) {
        this.light = light;
    }
    
    @Override
    public void execute() {
        previousState = light.isOn() ? 1 : 0;
        light.on();
    }
    
    @Override
    public void undo() {
        if (previousState == 0) {
            light.off();
        } else {
            light.on();
        }
    }
    
    @Override
    public void redo() {
        execute();
    }
}

// 具体命令：关闭电灯
public class LightOffCommand implements Command {
    
    private Light light;
    private int previousState;
    
    public LightOffCommand(Light light) {
        this.light = light;
    }
    
    @Override
    public void execute() {
        previousState = light.isOn() ? 1 : 0;
        light.off();
    }
    
    @Override
    public void undo() {
        if (previousState == 1) {
            light.on();
        } else {
            light.off();
        }
    }
    
    @Override
    public void redo() {
        execute();
    }
}

// 具体命令：风扇速度控制
public class FanCommand implements Command {
    
    public static final int HIGH = 3;
    public static final int MEDIUM = 2;
    public static final int LOW = 1;
    public static final int OFF = 0;
    
    private Fan fan;
    private int previousSpeed;
    private int targetSpeed;
    
    public FanCommand(Fan fan, int speed) {
        this.fan = fan;
        this.targetSpeed = speed;
    }
    
    @Override
    public void execute() {
        previousSpeed = fan.getSpeed();
        switch (targetSpeed) {
            case HIGH: fan.high(); break;
            case MEDIUM: fan.medium(); break;
            case LOW: fan.low(); break;
            case OFF: fan.off(); break;
        }
    }
    
    @Override
    public void undo() {
        switch (previousSpeed) {
            case HIGH: fan.high(); break;
            case MEDIUM: fan.medium(); break;
            case LOW: fan.low(); break;
            case OFF: fan.off(); break;
        }
    }
    
    @Override
    public void redo() {
        execute();
    }
}

// 调用者：遥控器
public class RemoteControl {
    
    private Command[] onCommands;
    private Command[] offCommands;
    private Command undoCommand;  // 撤销命令
    
    public RemoteControl() {
        // 5 个插槽
        onCommands = new Command[5];
        offCommands = new Command[5];
        
        // 默认空命令
        Command noCommand = new NoCommand();
        for (int i = 0; i < 5; i++) {
            onCommands[i] = noCommand;
            offCommands[i] = noCommand;
        }
        undoCommand = noCommand;
    }
    
    public void setCommand(int slot, Command onCommand, Command offCommand) {
        onCommands[slot] = onCommand;
        offCommands[slot] = offCommand;
    }
    
    public void onButtonPressed(int slot) {
        onCommands[slot].execute();
        undoCommand = onCommands[slot];
    }
    
    public void offButtonPressed(int slot) {
        offCommands[slot].execute();
        undoCommand = offCommands[slot];
    }
    
    public void undoButtonPressed() {
        undoCommand.undo();
    }
}

// 空命令（默认命令）
public class NoCommand implements Command {
    @Override
    public void execute() {}
    @Override
    public void undo() {}
    @Override
    public void redo() {}
}

// 测试
public class CommandTest {
    public static void main(String[] args) {
        // 创建设备
        Light livingRoomLight = new Light("客厅");
        Light bedroomLight = new Light("卧室");
        Fan ceilingFan = new Fan("客厅风扇");
        
        // 创建命令
        Command livingRoomOn = new LightOnCommand(livingRoomLight);
        Command livingRoomOff = new LightOffCommand(livingRoomLight);
        Command bedroomOn = new LightOnCommand(bedroomLight);
        Command fanHigh = new FanCommand(ceilingFan, FanCommand.HIGH);
        Command fanOff = new FanCommand(ceilingFan, FanCommand.OFF);
        
        // 创建遥控器并设置命令
        RemoteControl remote = new RemoteControl();
        remote.setCommand(0, livingRoomOn, livingRoomOff);
        remote.setCommand(1, bedroomOn, new LightOffCommand(bedroomLight));
        remote.setCommand(2, fanHigh, fanOff);
        
        // 使用遥控器
        System.out.println("=== 打开客厅灯 ===");
        remote.onButtonPressed(0);
        
        System.out.println("\n=== 打开卧室灯 ===");
        remote.onButtonPressed(1);
        
        System.out.println("\n=== 风扇高速 ===");
        remote.onButtonPressed(2);
        
        System.out.println("\n=== 撤销风扇 ===");
        remote.undoButtonPressed();
        
        System.out.println("\n=== 关闭客厅灯 ===");
        remote.offButtonPressed(0);
        
        System.out.println("\n=== 撤销 ===");
        remote.undoButtonPressed();
    }
}
```

## 三、宏命令（批量命令）

### 3.1 什么是宏命令

宏命令是一种特殊命令，它可以一次执行多个命令，非常适合场景化操作。

```java
// 宏命令：同时执行多个命令
public class MacroCommand implements Command {
    
    private Command[] commands;
    
    public MacroCommand(Command[] commands) {
        this.commands = commands;
    }
    
    @Override
    public void execute() {
        for (Command command : commands) {
            command.execute();
        }
    }
    
    @Override
    public void undo() {
        // 逆序撤销
        for (int i = commands.length - 1; i >= 0; i--) {
            commands[i].undo();
        }
    }
    
    @Override
    public void redo() {
        execute();
    }
}

// 使用
public class MacroTest {
    public static void main(String[] args) {
        Light light = new Light("客厅");
        Fan fan = new Fan("客厅风扇");
        
        // 创建"晚安"场景
        Command[] nightCommands = {
            new LightOffCommand(light),
            new FanCommand(fan, FanCommand.OFF)
        };
        MacroCommand nightScene = new MacroCommand(nightCommands);
        
        // 一键执行"晚安"场景
        nightScene.execute();
        // 输出：
        // 客厅 电灯关闭
        // 客厅风扇 风扇关闭
        
        // 一键撤销"晚安"场景
        nightScene.undo();
        // 输出：
        // 客厅风扇 风扇高速运转
        // 客厅 电灯打开
    }
}
```

### 3.2 动态宏命令

```java
// 动态宏命令
public class DynamicMacroCommand implements Command {
    
    private List<Command> commands = new ArrayList<>();
    
    public void addCommand(Command command) {
        commands.add(command);
    }
    
    public void removeCommand(Command command) {
        commands.remove(command);
    }
    
    @Override
    public void execute() {
        for (Command command : commands) {
            command.execute();
        }
    }
    
    @Override
    public void undo() {
        for (int i = commands.size() - 1; i >= 0; i--) {
            commands.get(i).undo();
        }
    }
    
    @Override
    public void redo() {
        execute();
    }
}
```

## 四、命令队列

### 4.1 命令排队执行

```java
// 命令队列
public class CommandQueue {
    
    private Queue<Command> queue = new LinkedList<>();
    
    public void addCommand(Command command) {
        queue.offer(command);
    }
    
    public void executeAll() {
        while (!queue.isEmpty()) {
            Command command = queue.poll();
            command.execute();
        }
    }
    
    public int size() {
        return queue.size();
    }
}

// 异步命令队列
public class AsyncCommandQueue {
    
    private BlockingQueue<Command> queue = new LinkedBlockingQueue<>();
    private ExecutorService executor;
    
    public AsyncCommandQueue() {
        executor = Executors.newSingleThreadExecutor();
        executor.submit(this::processQueue);
    }
    
    private void processQueue() {
        while (true) {
            try {
                Command command = queue.take();
                command.execute();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }
    
    public void addCommand(Command command) {
        queue.offer(command);
    }
    
    public void shutdown() {
        executor.shutdown();
    }
}
```

### 4.2 实际应用：任务队列

```java
// 任务命令
public class TaskCommand implements Command {
    
    private Task task;
    private TaskExecutor executor;
    
    public TaskCommand(Task task, TaskExecutor executor) {
        this.task = task;
        this.executor = executor;
    }
    
    @Override
    public void execute() {
        executor.execute(task);
    }
    
    @Override
    public void undo() {
        executor.cancel(task);
    }
    
    @Override
    public void redo() {
        executor.execute(task);
    }
}

// 任务执行器
public class TaskExecutor {
    
    private Map<String, Task> runningTasks = new ConcurrentHashMap<>();
    
    public void execute(Task task) {
        runningTasks.put(task.getId(), task);
        task.run();
    }
    
    public void cancel(Task task) {
        task.cancel();
        runningTasks.remove(task.getId());
    }
}
```

## 五、撤销与重做

### 5.1 简单撤销

```java
// 带状态的撤销
public class DrawCommand implements Command {
    
    private Canvas canvas;
    private Point point;
    private Color color;
    private Color previousColor;
    
    public DrawCommand(Canvas canvas, Point point, Color color) {
        this.canvas = canvas;
        this.point = point;
        this.color = color;
    }
    
    @Override
    public void execute() {
        previousColor = canvas.getColor(point);
        canvas.drawPoint(point, color);
    }
    
    @Override
    public void undo() {
        canvas.drawPoint(point, previousColor);
    }
    
    @Override
    public void redo() {
        execute();
    }
}
```

### 5.2 多级撤销

```java
// 撤销管理器
public class UndoManager {
    
    private Stack<Command> undoStack = new Stack<>();
    private Stack<Command> redoStack = new Stack<>();
    
    public void executeCommand(Command command) {
        command.execute();
        undoStack.push(command);
        redoStack.clear();  // 新命令清空重做栈
    }
    
    public void undo() {
        if (undoStack.isEmpty()) {
            System.out.println("没有可撤销的命令");
            return;
        }
        
        Command command = undoStack.pop();
        command.undo();
        redoStack.push(command);
    }
    
    public void redo() {
        if (redoStack.isEmpty()) {
            System.out.println("没有可重做的命令");
            return;
        }
        
        Command command = redoStack.pop();
        command.redo();
        undoStack.push(command);
    }
    
    public boolean canUndo() {
        return !undoStack.isEmpty();
    }
    
    public boolean canRedo() {
        return !redoStack.isEmpty();
    }
    
    public void clear() {
        undoStack.clear();
        redoStack.clear();
    }
}

// 文本编辑器命令
public class TextEditor {
    
    private StringBuilder text = new StringBuilder();
    private UndoManager undoManager = new UndoManager();
    private int cursorPosition = 0;
    
    public void type(String chars) {
        Command command = new TypeCommand(this, chars);
        undoManager.executeCommand(command);
        cursorPosition += chars.length();
    }
    
    public void delete(int count) {
        Command command = new DeleteCommand(this, count);
        undoManager.executeCommand(command);
        cursorPosition = Math.max(0, cursorPosition - count);
    }
    
    public void undo() {
        undoManager.undo();
    }
    
    public void redo() {
        undoManager.redo();
    }
    
    public String getText() {
        return text.toString();
    }
    
    public int getCursor() {
        return cursorPosition;
    }
}

// 插入命令
public class TypeCommand implements Command {
    
    private TextEditor editor;
    private String chars;
    private String insertedText = "";
    
    public TypeCommand(TextEditor editor, String chars) {
        this.editor = editor;
        this.chars = chars;
    }
    
    @Override
    public void execute() {
        editor.getTextBuilder().append(chars);
        insertedText = chars;
    }
    
    @Override
    public void undo() {
        String current = editor.getText();
        int cursor = editor.getCursor();
        editor.setText(current.substring(0, cursor - insertedText.length()));
    }
    
    @Override
    public void redo() {
        execute();
    }
}
```

## 六、实战案例

### 6.1 订单系统

```java
// 订单命令接口
public interface OrderCommand {
    void execute();
    void cancel();
}

// 订单
public class Order {
    private String orderId;
    private double amount;
    private String status;
    
    // getters and setters
    public String getOrderId() { return orderId; }
    public double getAmount() { return amount; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}

// 创建订单命令
public class CreateOrderCommand implements OrderCommand {
    
    private Order order;
    private OrderRepository repository;
    
    public CreateOrderCommand(Order order, OrderRepository repository) {
        this.order = order;
        this.repository = repository;
    }
    
    @Override
    public void execute() {
        order.setStatus("CREATED");
        repository.save(order);
        System.out.println("订单已创建: " + order.getOrderId());
    }
    
    @Override
    public void cancel() {
        order.setStatus("CANCELLED");
        repository.update(order);
        System.out.println("订单已取消: " + order.getOrderId());
    }
}

// 支付命令
public class PayOrderCommand implements OrderCommand {
    
    private Order order;
    private PaymentService paymentService;
    
    public PayOrderCommand(Order order, PaymentService paymentService) {
        this.order = order;
        this.paymentService = paymentService;
    }
    
    @Override
    public void execute() {
        paymentService.pay(order);
        order.setStatus("PAID");
        System.out.println("订单已支付: " + order.getOrderId());
    }
    
    @Override
    public void cancel() {
        paymentService.refund(order);
        order.setStatus("REFUNDED");
        System.out.println("订单已退款: " + order.getOrderId());
    }
}

// 订单处理器
public class OrderProcessor {
    
    private List<OrderCommand> commandHistory = new ArrayList<>();
    
    public void process(OrderCommand command) {
        command.execute();
        commandHistory.add(command);
    }
    
    public void cancelLast() {
        if (!commandHistory.isEmpty()) {
            OrderCommand last = commandHistory.remove(commandHistory.size() - 1);
            last.cancel();
        }
    }
}

// 服务类
class OrderRepository {
    public void save(Order order) { /* 保存到数据库 */ }
    public void update(Order order) { /* 更新数据库 */ }
}

class PaymentService {
    public void pay(Order order) { /* 调用支付接口 */ }
    public void refund(Order order) { /* 调用退款接口 */ }
}
```

### 6.2 文件操作

```java
// 文件操作命令
public interface FileOperation {
    void execute();
    void undo();
}

// 文件系统
public class FileSystem {
    
    private String currentDir = "/home/user";
    private Map<String, String> files = new HashMap<>();
    
    public void createFile(String name, String content) {
        files.put(name, content);
        System.out.println("创建文件: " + name);
    }
    
    public void deleteFile(String name) {
        files.remove(name);
        System.out.println("删除文件: " + name);
    }
    
    public String readFile(String name) {
        return files.getOrDefault(name, "");
    }
}

// 创建文件命令
public class CreateFileCommand implements FileOperation {
    
    private FileSystem fs;
    private String fileName;
    private String content;
    private String deletedContent;  // 用于撤销
    
    public CreateFileCommand(FileSystem fs, String fileName, String content) {
        this.fs = fs;
        this.fileName = fileName;
        this.content = content;
    }
    
    @Override
    public void execute() {
        fs.createFile(fileName, content);
    }
    
    @Override
    public void undo() {
        fs.deleteFile(fileName);
        System.out.println("撤销: 删除文件 " + fileName);
    }
}

// 删除文件命令
public class DeleteFileCommand implements FileOperation {
    
    private FileSystem fs;
    private String fileName;
    private String content;  // 保存内容用于恢复
    
    public DeleteFileCommand(FileSystem fs, String fileName) {
        this.fs = fs;
        this.fileName = fileName;
        this.content = fs.readFile(fileName);
    }
    
    @Override
    public void execute() {
        fs.deleteFile(fileName);
    }
    
    @Override
    public void undo() {
        fs.createFile(fileName, content);
        System.out.println("撤销: 恢复文件 " + fileName);
    }
}

// 批量操作命令
public class BatchCommand implements FileOperation {
    
    private List<FileOperation> operations = new ArrayList<>();
    
    public void add(FileOperation op) {
        operations.add(op);
    }
    
    @Override
    public void execute() {
        for (FileOperation op : operations) {
            op.execute();
        }
    }
    
    @Override
    public void undo() {
        // 逆序撤销
        for (int i = operations.size() - 1; i >= 0; i--) {
            operations.get(i).undo();
        }
    }
}
```

### 6.3 数据库事务

```java
// 事务命令
public interface TransactionCommand {
    void execute();
    void rollback();
}

// 数据库
public class Database {
    
    private Map<String, Map<String, Object>> tables = new HashMap<>();
    
    public void insert(String table, String id, Map<String, Object> data) {
        tables.computeIfAbsent(table, k -> new HashMap<>()).put(id, data);
    }
    
    public void update(String table, String id, String field, Object value) {
        Map<String, Object> row = tables.get(table).get(id);
        if (row != null) {
            row.put(field, value);
        }
    }
    
    public void delete(String table, String id) {
        Map<String, Object> tableData = tables.get(table);
        if (tableData != null) {
            tableData.remove(id);
        }
    }
    
    public Map<String, Object> query(String table, String id) {
        return tables.get(table).get(id);
    }
}

// 更新命令
public class UpdateCommand implements TransactionCommand {
    
    private Database db;
    private String table;
    private String id;
    private String field;
    private Object newValue;
    private Object oldValue;
    
    public UpdateCommand(Database db, String table, String id, 
            String field, Object newValue) {
        this.db = db;
        this.table = table;
        this.id = id;
        this.field = field;
        this.newValue = newValue;
    }
    
    @Override
    public void execute() {
        Map<String, Object> row = db.query(table, id);
        oldValue = row.get(field);
        db.update(table, id, field, newValue);
        System.out.println("更新: " + table + "." + id + "." + field);
    }
    
    @Override
    public void rollback() {
        db.update(table, id, field, oldValue);
        System.out.println("回滚: " + table + "." + id + "." + field);
    }
}

// 事务管理器
public class TransactionManager {
    
    private List<TransactionCommand> commands = new ArrayList<>();
    
    public void addCommand(TransactionCommand command) {
        commands.add(command);
    }
    
    public void commit() {
        for (TransactionCommand cmd : commands) {
            cmd.execute();
        }
        commands.clear();
    }
    
    public void rollback() {
        // 逆序回滚
        for (int i = commands.size() - 1; i >= 0; i--) {
            commands.get(i).rollback();
        }
        commands.clear();
    }
}
```

## 七、命令模式 vs 其他模式

### 7.1 对比

| 维度 | 命令模式 | 策略模式 | 责任链模式 |
|------|---------|---------|-----------|
| **目的** | 请求封装/撤销 | 算法替换 | 请求传递 |
| **调用关系** | 调用者→命令→接收者 | 上下文→策略 | 链式传递 |
| **撤销支持** | 原生支持 | 不支持 | 不支持 |
| **队列支持** | 原生支持 | 不支持 | 可选 |

### 7.2 组合使用

```java
// 命令 + 责任链
public class CommandChain {
    
    private Handler first;
    private Handler last;
    
    public void addHandler(Handler handler) {
        if (first == null) {
            first = last = handler;
        } else {
            last.setNext(handler);
            last = handler;
        }
    }
    
    public void process(Command command) {
        if (first != null) {
            first.handle(command);
        }
    }
}

// 命令 + 观察者
public class ObservableCommand implements Command {
    
    private Command delegate;
    private List<CommandObserver> observers = new ArrayList<>();
    
    public ObservableCommand(Command delegate) {
        this.delegate = delegate;
    }
    
    public void addObserver(CommandObserver observer) {
        observers.add(observer);
    }
    
    @Override
    public void execute() {
        notifyBefore();
        delegate.execute();
        notifyAfter();
    }
    
    private void notifyBefore() {
        for (CommandObserver obs : observers) {
            obs.beforeExecute(this);
        }
    }
    
    private void notifyAfter() {
        for (CommandObserver obs : observers) {
            obs.afterExecute(this);
        }
    }
}

interface CommandObserver {
    void beforeExecute(Command command);
    void afterExecute(Command command);
}
```

## 八、源码中的应用

### 8.1 JDK - Runnable

```java
// Runnable 就是一个简单的命令接口
public interface Runnable {
    void run();
}

// Thread 接收命令并执行
public class Thread implements Runnable {
    private Runnable target;
    
    public void run() {
        if (target != null) {
            target.run();
        }
    }
}

// Executor 执行命令
public interface Executor {
    void execute(Runnable command);
}
```

### 8.2 Spring - TransactionTemplate

```java
// Spring 的编程式事务
public class TransactionTemplate {
    
    private PlatformTransactionManager transactionManager;
    
    public <T> T execute(TransactionCallback<T> action) {
        TransactionStatus status = transactionManager.getTransaction(null);
        try {
            T result = action.doInTransaction(status);
            transactionManager.commit(status);
            return result;
        } catch (Exception e) {
            transactionManager.rollback(status);
            throw e;
        }
    }
}

// 命令模式体现
public interface TransactionCallback<T> {
    T doInTransaction(TransactionStatus status);
}

// 使用
TransactionTemplate template = new TransactionTemplate();
template.execute(status -> {
    // 业务逻辑
    return null;
});
```

### 8.3 数据库 JDBC

```java
// PreparedStatement 就是命令模式
Connection conn = DriverManager.getConnection(url);
PreparedStatement ps = conn.prepareStatement("INSERT INTO users VALUES (?, ?)");

// 设置参数（命令参数化）
ps.setString(1, "John");
ps.setString(2, "john@email.com");

// 执行命令
ps.executeUpdate();

// 可以多次执行同一命令（不同参数）
ps.setString(1, "Jane");
ps.executeUpdate();
```

### 8.4 Spring MVC Controller

```java
// Spring MVC 的 @RequestMapping 就是命令模式
@Controller
public class UserController {
    
    @RequestMapping("/users")
    public String listUsers(Model model) {
        // 命令参数化：不同的 URL 执行不同的逻辑
        List<User> users = userService.findAll();
        model.addAttribute("users", users);
        return "user/list";
    }
}
```

## 九、面试常见问题

### Q1：命令模式和策略模式的区别？

| 维度 | 命令模式 | 策略模式 |
|------|---------|---------|
| **目的** | 封装请求 | 替换算法 |
| **撤销支持** | 原生 | 不支持 |
| **历史记录** | 支持 | 不支持 |
| **调用者** | 持有命令引用 | 不持有 |

### Q2：命令模式有什么优点？

1. **解耦**：发送者和接收者解耦
2. **可撤销**：支持撤销/重做
3. **可排队**：命令可以排队执行
4. **可日志**：可以记录命令执行历史
5. **可组合**：可以组合多个命令

### Q3：如何实现多级撤销？

使用两个栈：一个存储已执行的命令，一个存储已撤销的命令。执行新命令时清空重做栈。

### Q4：命令模式和职责链的区别？

| 维度 | 命令模式 | 职责链 |
|------|---------|--------|
| **处理方式** | 单个命令执行 | 链式传递 |
| **撤销支持** | 支持 | 不支持 |
| **组合方式** | 宏命令组合 | 链式组合 |

## 十、总结

### 核心要点

```
命令模式：
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Invoker ──→ Command ──→ Receiver                          │
│  (调用者)    (命令)      (接收者)                            │
│                                                             │
│  关键点：                                                    │
│  • 请求封装为对象                                           │
│  • 支持撤销/重做                                            │
│  • 支持命令排队                                             │
│  • 支持日志记录                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 与其他模式对比

| 模式 | 目的 | 撤销支持 |
|------|------|---------|
| 命令模式 | 请求封装 | ✅ |
| 策略模式 | 算法替换 | ❌ |
| 职责链 | 请求传递 | ❌ |
| 观察者 | 通知机制 | ❌ |

## 结语

命令模式是实现撤销/重做、命令队列、日志记录等功能的基础。掌握命令模式，能够设计出更灵活、更易维护的系统。

**下期预告**：迭代器模式（Iterator Pattern）

> 记住：**命令模式让请求变成可撤销的对象**。
