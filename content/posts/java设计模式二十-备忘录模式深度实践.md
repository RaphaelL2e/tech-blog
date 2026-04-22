---
title: "Java设计模式（二十）：备忘录模式深度实践"
date: 2026-04-22T11:00:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "备忘录模式", "memento", "撤销", "快照"]
---

## 前言

备忘录模式（Memento Pattern）是一种行为型设计模式，它的核心思想是：**在不破坏封装性的前提下，捕获一个对象的内部状态，并在该对象之外保存这个状态，以便以后恢复**。

**核心思想**：保存对象快照，支持撤销/恢复。

<!--more-->

## 一、为什么需要备忘录模式

### 1.1 撤销功能的需求

假设我们在开发一个文本编辑器，需要支持撤销操作：

```java
// 不用备忘录模式：直接暴露内部状态
public class TextEditor {
    private String text;
    private int cursor;
    
    // 暴露了内部实现细节，破坏封装
    public String getText() { return text; }
    public int getCursor() { return cursor; }
    public void setText(String text) { this.text = text; }
    public void setCursor(int cursor) { this.cursor = cursor; }
}
```

直接暴露内部状态破坏了封装性。备忘录模式通过将状态封装在备忘录对象中来解决这个问题。

### 1.2 原则：不破坏封装

备忘录模式的核心约束：备忘录对象由原发器（Originator）创建和读取，其他对象（包括负责者 Caretaker）不能访问备忘录的内部状态。

## 二、备忘录模式的结构

### 2.1 类图

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Originator      │    │    Memento       │    │   Caretaker      │
│  (原发器)        │    │   (备忘录)       │    │   (负责者)       │
│──────────────────│    │──────────────────│    │──────────────────│
│ - state          │◄──→│ - state          │◄──→│ - mementos: List │
│──────────────────│    │──────────────────│    │──────────────────│
│ + createMemento()│    │ + getState()     │    │ + addMemento()   │
│ + restore()      │    │ (仅Originator可调)│    │ + getMemento()   │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 2.2 核心角色

| 角色 | 职责 |
|------|------|
| Originator（原发器） | 创建备忘录，从备忘录恢复状态 |
| Memento（备忘录） | 存储原发器的内部状态 |
| Caretaker（负责者） | 保管备忘录，不操作备忘录内容 |

### 2.3 完整实现

```java
// ========== 1. 备忘录 ==========
public class EditorMemento {
    private final String text;
    private final int cursorPosition;
    private final LocalDateTime timestamp;
    
    public EditorMemento(String text, int cursorPosition) {
        this.text = text;
        this.cursorPosition = cursorPosition;
        this.timestamp = LocalDateTime.now();
    }
    
    // 只有同包的 Originator 可以访问（包私有或友元）
    String getSavedText() { return text; }
    int getSavedCursorPosition() { return cursorPosition; }
    
    public LocalDateTime getTimestamp() { return timestamp; }
    
    @Override
    public String toString() {
        return "快照[" + timestamp + "]: \"" + 
            (text.length() > 20 ? text.substring(0, 20) + "..." : text) + 
            "\" 光标=" + cursorPosition;
    }
}

// ========== 2. 原发器：文本编辑器 ==========
public class TextEditor {
    private StringBuilder text = new StringBuilder();
    private int cursorPosition = 0;
    
    public void type(String content) {
        text.insert(cursorPosition, content);
        cursorPosition += content.length();
        System.out.println("📝 输入: \"" + content + "\" → 当前文本: \"" + text + "\"");
    }
    
    public void delete(int count) {
        int start = Math.max(0, cursorPosition - count);
        String deleted = text.substring(start, cursorPosition);
        text.delete(start, cursorPosition);
        cursorPosition = start;
        System.out.println("🗑️ 删除: \"" + deleted + "\" → 当前文本: \"" + text + "\"");
    }
    
    // 创建备忘录
    public EditorMemento save() {
        System.out.println("💾 保存快照");
        return new EditorMemento(text.toString(), cursorPosition);
    }
    
    // 从备忘录恢复
    public void restore(EditorMemento memento) {
        this.text = new StringBuilder(memento.getSavedText());
        this.cursorPosition = memento.getSavedCursorPosition();
        System.out.println("↩️ 恢复快照 → 当前文本: \"" + text + "\"");
    }
    
    public String getText() { return text.toString(); }
}

// ========== 3. 负责者：历史管理器 ==========
public class EditorHistory {
    private final Deque<EditorMemento> history = new ArrayDeque<>();
    private static final int MAX_HISTORY = 50;
    
    public void push(EditorMemento memento) {
        if (history.size() >= MAX_HISTORY) {
            history.removeLast();
        }
        history.push(memento);
    }
    
    public EditorMemento pop() {
        if (history.isEmpty()) {
            throw new IllegalStateException("没有可撤销的操作");
        }
        return history.pop();
    }
    
    public boolean canUndo() { return !history.isEmpty(); }
    
    public int size() { return history.size(); }
    
    public void printHistory() {
        System.out.println("📋 历史记录 (" + history.size() + " 条):");
        history.forEach(m -> System.out.println("  " + m));
    }
}

// ========== 4. 客户端 ==========
public class EditorDemo {
    public static void main(String[] args) {
        TextEditor editor = new TextEditor();
        EditorHistory history = new EditorHistory();
        
        // 保存初始状态
        history.push(editor.save());
        
        editor.type("Hello");
        history.push(editor.save());
        
        editor.type(" World");
        history.push(editor.save());
        
        editor.type("!");
        
        // 撤销
        System.out.println("\n--- 撤销 ---");
        editor.restore(history.pop());
        editor.restore(history.pop());
        
        System.out.println("\n当前文本: " + editor.getText());
    }
}
```

## 三、备忘录模式的高级用法

### 3.1 带重做的备忘录

```java
public class UndoRedoHistory {
    private final Deque<EditorMemento> undoStack = new ArrayDeque<>();
    private final Deque<EditorMemento> redoStack = new ArrayDeque<>();
    
    public void save(EditorMemento memento) {
        undoStack.push(memento);
        redoStack.clear();  // 新操作清空重做栈
    }
    
    public EditorMemento undo(EditorMemento currentState) {
        if (undoStack.isEmpty()) throw new IllegalStateException("无法撤销");
        redoStack.push(currentState);
        return undoStack.pop();
    }
    
    public EditorMemento redo(EditorMemento currentState) {
        if (redoStack.isEmpty()) throw new IllegalStateException("无法重做");
        undoStack.push(currentState);
        return redoStack.pop();
    }
    
    public boolean canUndo() { return !undoStack.isEmpty(); }
    public boolean canRedo() { return !redoStack.isEmpty(); }
}
```

### 3.2 增量备忘录

对于大对象，可以只保存变化的部分：

```java
public class IncrementalMemento {
    private final String delta;  // 只保存变化量
    private final int position;
    
    public IncrementalMemento(String delta, int position) {
        this.delta = delta;
        this.position = position;
    }
    
    public String getDelta() { return delta; }
    public int getPosition() { return position; }
}

public class IncrementalEditor {
    private StringBuilder text = new StringBuilder();
    private final Deque<IncrementalMemento> history = new ArrayDeque<>();
    
    public void type(String content) {
        int pos = text.length();
        text.append(content);
        // 保存增量：操作是"添加"，反向操作是"删除"
        history.push(new IncrementalMemento(content, pos));
    }
    
    public void undo() {
        IncrementalMemento memento = history.pop();
        text.delete(memento.getPosition(), 
            memento.getPosition() + memento.getDelta().length());
    }
}
```

### 3.3 序列化备忘录

将备忘录序列化存储，支持持久化：

```java
public class SerializableMemento implements Serializable {
    private final byte[] stateData;
    private final LocalDateTime timestamp;
    
    public SerializableMemento(Serializable state) {
        this.timestamp = LocalDateTime.now();
        try (ByteArrayOutputStream bos = new ByteArrayOutputStream();
             ObjectOutputStream oos = new ObjectOutputStream(bos)) {
            oos.writeObject(state);
            this.stateData = bos.toByteArray();
        } catch (IOException e) {
            throw new RuntimeException("序列化失败", e);
        }
    }
    
    @SuppressWarnings("unchecked")
    public <T> T getState() {
        try (ByteArrayInputStream bis = new ByteArrayInputStream(stateData);
             ObjectInputStream ois = new ObjectInputStream(bis)) {
            return (T) ois.readObject();
        } catch (IOException | ClassNotFoundException e) {
            throw new RuntimeException("反序列化失败", e);
        }
    }
}
```

## 四、备忘录模式在 JDK 中的应用

### 4.1 java.io.Serializable

序列化机制可以看作备忘录模式的变体：

```java
// 将对象状态保存到字节流（备忘录）
ByteArrayOutputStream bos = new ByteArrayOutputStream();
ObjectOutputStream oos = new ObjectOutputStream(bos);
oos.writeObject(myObject);
byte[] memento = bos.toByteArray();  // 备忘录

// 从字节流恢复对象状态
ByteArrayInputStream bis = new ByteArrayInputStream(memento);
ObjectInputStream ois = new ObjectInputStream(bis);
MyObject restored = (MyObject) ois.readObject();  // 恢复
```

### 4.2 java.util.Date 的克隆

```java
Date original = new Date();
Date memento = (Date) original.clone();  // 快照
// 修改 original...
Date restored = memento;  // 恢复
```

## 五、备忘录模式 vs 其他模式

### 5.1 对比命令模式

| 维度 | 备忘录模式 | 命令模式 |
|------|---------|---------|
| 保存内容 | 对象完整状态 | 操作本身 |
| 撤销方式 | 恢复到之前的状态 | 执行反向操作 |
| 内存占用 | 较大（完整状态） | 较小（只有操作） |
| 适用场景 | 需要任意回退 | 操作有明确反向操作 |

### 5.2 对比原型模式

| 维度 | 备忘录模式 | 原型模式 |
|------|---------|---------|
| 目的 | 保存状态以便恢复 | 克隆创建新对象 |
| 对象 | 备忘录不是完整对象 | 克隆出完整对象 |
| 使用 | 临时保存，后续恢复 | 创建新的独立对象 |

## 六、备忘录模式的优缺点

### 优点

1. **不破坏封装**：状态保存在备忘录中，不暴露内部细节
2. **简化原发器**：原发器不需要自己管理状态历史
3. **支持撤销**：可以恢复到任意历史状态

### 缺点

1. **内存开销**：保存完整状态可能消耗大量内存
2. **性能问题**：频繁创建备忘录有性能开销
3. **维护成本**：原发器状态变化时需要更新备忘录结构

### 适用场景

- 需要保存和恢复对象状态
- 需要实现撤销/重做功能
- 需要提供事务回滚机制
- 需要保存对象在某个时刻的快照

## 七、实战：游戏存档系统

用备忘录模式实现游戏存档：

```java
// ========== 备忘录：游戏存档 ==========
public class GameSave {
    private final int level;
    private final int health;
    private final int mana;
    private final int score;
    private final List<String> inventory;
    private final String checkpoint;
    private final LocalDateTime saveTime;
    
    public GameSave(int level, int health, int mana, int score, 
                    List<String> inventory, String checkpoint) {
        this.level = level;
        this.health = health;
        this.mana = mana;
        this.score = score;
        this.inventory = new ArrayList<>(inventory);
        this.checkpoint = checkpoint;
        this.saveTime = LocalDateTime.now();
    }
    
    // Getters (包私有，只有 GameCharacter 可访问)
    int getLevel() { return level; }
    int getHealth() { return health; }
    int getMana() { return mana; }
    int getScore() { return score; }
    List<String> getInventory() { return inventory; }
    String getCheckpoint() { return checkpoint; }
    public LocalDateTime getSaveTime() { return saveTime; }
    
    @Override
    public String toString() {
        return "🎮 存档[" + saveTime + "] Lv." + level + 
            " HP=" + health + " MP=" + mana + " 分数=" + score + 
            " 物品=" + inventory + " 检查点=" + checkpoint;
    }
}

// ========== 原发器：游戏角色 ==========
public class GameCharacter {
    private int level = 1;
    private int health = 100;
    private int mana = 50;
    private int score = 0;
    private List<String> inventory = new ArrayList<>();
    private String checkpoint = "起始村庄";
    
    public void levelUp() {
        level++;
        health += 20;
        mana += 10;
        System.out.println("⬆️ 升级！当前等级: " + level);
    }
    
    public void takeDamage(int damage) {
        health = Math.max(0, health - damage);
        System.out.println("💥 受到 " + damage + " 伤害，剩余 HP: " + health);
    }
    
    public void addItem(String item) {
        inventory.add(item);
        System.out.println("🎁 获得物品: " + item);
    }
    
    public void addScore(int points) {
        score += points;
        System.out.println("🏆 获得 " + points + " 分，总分: " + score);
    }
    
    public void setCheckpoint(String checkpoint) {
        this.checkpoint = checkpoint;
        System.out.println("📍 到达检查点: " + checkpoint);
    }
    
    public GameSave save() {
        System.out.println("💾 保存游戏...");
        return new GameSave(level, health, mana, score, inventory, checkpoint);
    }
    
    public void load(GameSave save) {
        this.level = save.getLevel();
        this.health = save.getHealth();
        this.mana = save.getMana();
        this.score = save.getScore();
        this.inventory = new ArrayList<>(save.getInventory());
        this.checkpoint = save.getCheckpoint();
        System.out.println("📂 加载存档: Lv." + level + " HP=" + health);
    }
    
    public void printStatus() {
        System.out.println("📊 状态: Lv." + level + " HP=" + health + 
            " MP=" + mana + " 分数=" + score + " 检查点=" + checkpoint);
    }
}

// ========== 负责者：存档管理器 ==========
public class SaveManager {
    private final Map<String, GameSave> saves = new LinkedHashMap<>();
    
    public void save(String slot, GameSave save) {
        saves.put(slot, save);
        System.out.println("💾 存档已保存到槽位: " + slot);
    }
    
    public GameSave load(String slot) {
        GameSave save = saves.get(slot);
        if (save == null) throw new IllegalArgumentException("槽位 " + slot + " 无存档");
        System.out.println("📂 从槽位 " + slot + " 加载存档");
        return save;
    }
    
    public void listSaves() {
        System.out.println("📋 存档列表:");
        saves.forEach((slot, save) -> 
            System.out.println("  槽位[" + slot + "] " + save));
    }
}

// ========== 客户端 ==========
public class GameDemo {
    public static void main(String[] args) {
        GameCharacter hero = new GameCharacter();
        SaveManager saveManager = new SaveManager();
        
        // 游戏开始
        hero.addItem("木剑");
        hero.setCheckpoint("起始村庄");
        saveManager.save("slot1", hero.save());
        
        // 冒险
        hero.levelUp();
        hero.addItem("铁盾");
        hero.takeDamage(30);
        hero.addScore(500);
        hero.setCheckpoint("黑暗森林");
        saveManager.save("slot2", hero.save());
        
        // 继续冒险
        hero.levelUp();
        hero.addItem("魔法书");
        hero.takeDamage(80);
        hero.printStatus();  // HP 很低
        
        // 读取之前的存档
        System.out.println("\n--- 读取存档 ---");
        hero.load(saveManager.load("slot2"));
        hero.printStatus();
        
        saveManager.listSaves();
    }
}
```

## 八、备忘录模式在 Spring 中的应用

### 8.1 事务管理

Spring 的事务管理隐含了备忘录思想——在事务开始时保存状态，失败时回滚：

```java
@Transactional
public void transfer(Long from, Long to, BigDecimal amount) {
    // Spring 在事务开始时隐含"保存快照"
    accountDao.debit(from, amount);
    accountDao.credit(to, amount);
    // 如果异常 → 回滚（恢复到事务开始前的状态）
}
```

## 九、面试常见问题

### Q1: 备忘录模式的核心思想是什么？

备忘录模式在不破坏封装的前提下，捕获对象的内部状态并保存在外部，以便后续恢复。三个核心角色：原发器（创建/恢复备忘录）、备忘录（存储状态）、负责者（保管备忘录）。

### Q2: 如何保证备忘录的封装性？

可以通过以下方式：1) 备忘录的内部状态设为包私有，只有同包的原发器可以访问；2) 备忘录定义为一个内部类；3) 使用 Java 9+ 的模块系统限制访问。关键是负责者不能修改备忘录内容。

### Q3: 备忘录模式和命令模式都能实现撤销，怎么选？

如果操作有明确的反向操作（如加→减），使用命令模式，内存占用小。如果操作无法反转或需要恢复到任意历史状态，使用备忘录模式，但内存占用大。两者也可以结合使用。

### Q4: 备忘录模式在内存方面有什么问题？

每次保存完整状态可能消耗大量内存，特别是对象状态较大时。解决方案：1) 增量备忘录（只保存变化部分）；2) 限制历史数量；3) 序列化到磁盘；4) 结合原型模式做深拷贝。

### Q5: 如何实现重做（Redo）功能？

维护两个栈：撤销栈和重做栈。撤销时将当前状态压入重做栈，从撤销栈弹出恢复。新操作时清空重做栈。重做时将当前状态压入撤销栈，从重做栈弹出恢复。

## 十、总结

备忘录模式是实现"撤销/恢复"功能的标准方案，它在不破坏封装的前提下保存和恢复对象状态。

**核心要点**：

1. **保存快照**：捕获对象在某一时刻的完整状态
2. **不破坏封装**：备忘录对外不可见内部结构
3. **三角色协作**：原发器创建、备忘录存储、负责者保管
4. **撤销/重做**：最常见的应用场景
5. **注意内存**：完整状态保存可能消耗大量内存

备忘录模式告诉我们：有时候最简单的"存起来，需要时恢复"就是最好的解决方案。

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
- [Java设计模式（十六）：外观模式实战解析](/posts/java设计模式十六-外观模式实战解析/)
- [Java设计模式（十七）：代理模式深度实践](/posts/java设计模式十七-代理模式深度实践/)
- [Java设计模式（十八）：桥接模式深度实践](/posts/java设计模式十八-桥接模式深度实践/)
- [Java设计模式（十九）：中介者模式深度实践](/posts/java设计模式十九-中介者模式深度实践/)
