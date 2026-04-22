---
title: "Java设计模式（二十二）：解释器模式实战解析"
date: 2026-04-22T11:20:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "解释器模式", "interpreter", "DSL", "语法树"]
---

## 前言

解释器模式（Interpreter Pattern）是一种行为型设计模式，它的核心思想是：**给定一个语言，定义它的文法的一种表示，并定义一个解释器，这个解释器使用该表示来解释语言中的句子**。

**核心思想**：用类来表示文法规则，通过组合这些类来解释表达式。

<!--more-->

## 一、为什么需要解释器模式

### 1.1 领域特定语言（DSL）

在许多应用中，我们需要解析特定领域的表达式：

- SQL 查询条件：`age > 18 AND name = 'Alice'`
- 配置规则：`env == "prod" AND region IN ["us", "eu"]`
- 数学表达式：`(1 + 2) * 3 - 4`
- 权限规则：`role == "admin" OR (role == "user" AND department == "IT")`

解释器模式将这些表达式的文法规则映射为类，通过组合类来构建和解释表达式。

### 1.2 文法与类的关系

解释器模式的核心思想：**每一条文法规则对应一个类**。

```
文法: Expression ::= Terminal | OrExpression | AndExpression
类:   Expression  ←  Terminal  |  OrExpression  |  AndExpression
```

## 二、解释器模式的结构

### 2.1 类图

```
┌─────────────────────────┐
│  AbstractExpression     │
│─────────────────────────│
│ + interpret(Context)    │
└───────────┬─────────────┘
            │
    ┌───────┼───────┐
    │       │       │
┌───┴────┐ ┌┴──────┐ ┌──────────────────┐
│Terminal│ │NonTer-│ │  Context         │
│Express │ │minal  │ │──────────────────│
│        │ │Express│ │ 全局信息/变量表  │
└────────┘ │───────│ └──────────────────┘
           │expr1  │
           │expr2  │
           └───────┘
```

### 2.2 核心角色

| 角色 | 职责 |
|------|------|
| AbstractExpression | 声明解释操作 |
| TerminalExpression | 终结符表达式（叶子节点） |
| NonTerminalExpression | 非终结符表达式（组合节点） |
| Context | 上下文，存储全局信息 |

### 2.3 完整实现：布尔表达式解释器

```java
// ========== 1. 上下文 ==========
public class Context {
    private final Map<String, Boolean> variables = new HashMap<>();
    
    public void assign(String name, boolean value) {
        variables.put(name, value);
    }
    
    public boolean lookup(String name) {
        if (!variables.containsKey(name)) {
            throw new IllegalArgumentException("未知变量: " + name);
        }
        return variables.get(name);
    }
}

// ========== 2. 抽象表达式 ==========
public interface BooleanExpression {
    boolean interpret(Context context);
}

// ========== 3. 终结符：变量 ==========
public class VariableExpression implements BooleanExpression {
    private final String name;
    
    public VariableExpression(String name) {
        this.name = name;
    }
    
    @Override
    public boolean interpret(Context context) {
        return context.lookup(name);
    }
    
    @Override
    public String toString() { return name; }
}

// ========== 4. 终结符：常量 ==========
public class ConstantExpression implements BooleanExpression {
    private final boolean value;
    
    public ConstantExpression(boolean value) {
        this.value = value;
    }
    
    @Override
    public boolean interpret(Context context) {
        return value;
    }
    
    @Override
    public String toString() { return String.valueOf(value); }
}

// ========== 5. 非终结符：AND ==========
public class AndExpression implements BooleanExpression {
    private final BooleanExpression left;
    private final BooleanExpression right;
    
    public AndExpression(BooleanExpression left, BooleanExpression right) {
        this.left = left;
        this.right = right;
    }
    
    @Override
    public boolean interpret(Context context) {
        return left.interpret(context) && right.interpret(context);
    }
    
    @Override
    public String toString() { return "(" + left + " AND " + right + ")"; }
}

// ========== 6. 非终结符：OR ==========
public class OrExpression implements BooleanExpression {
    private final BooleanExpression left;
    private final BooleanExpression right;
    
    public OrExpression(BooleanExpression left, BooleanExpression right) {
        this.left = left;
        this.right = right;
    }
    
    @Override
    public boolean interpret(Context context) {
        return left.interpret(context) || right.interpret(context);
    }
    
    @Override
    public String toString() { return "(" + left + " OR " + right + ")"; }
}

// ========== 7. 非终结符：NOT ==========
public class NotExpression implements BooleanExpression {
    private final BooleanExpression expression;
    
    public NotExpression(BooleanExpression expression) {
        this.expression = expression;
    }
    
    @Override
    public boolean interpret(Context context) {
        return !expression.interpret(context);
    }
    
    @Override
    public String toString() { return "NOT(" + expression + ")"; }
}

// ========== 8. 客户端 ==========
public class BooleanInterpreterDemo {
    public static void main(String[] args) {
        // 构建表达式：(isAdmin OR isEditor) AND NOT(isBanned)
        BooleanExpression expr = new AndExpression(
            new OrExpression(
                new VariableExpression("isAdmin"),
                new VariableExpression("isEditor")
            ),
            new NotExpression(
                new VariableExpression("isBanned")
            )
        );
        
        System.out.println("表达式: " + expr);
        
        // 场景1：管理员，未封禁
        Context ctx1 = new Context();
        ctx1.assign("isAdmin", true);
        ctx1.assign("isEditor", false);
        ctx1.assign("isBanned", false);
        System.out.println("场景1: " + expr.interpret(ctx1));  // true
        
        // 场景2：编辑者，但被封禁
        Context ctx2 = new Context();
        ctx2.assign("isAdmin", false);
        ctx2.assign("isEditor", true);
        ctx2.assign("isBanned", true);
        System.out.println("场景2: " + expr.interpret(ctx2));  // false
        
        // 场景3：普通用户
        Context ctx3 = new Context();
        ctx3.assign("isAdmin", false);
        ctx3.assign("isEditor", false);
        ctx3.assign("isBanned", false);
        System.out.println("场景3: " + expr.interpret(ctx3));  // false
    }
}
```

运行结果：

```
表达式: ((isAdmin OR isEditor) AND NOT(isBanned))
场景1: true
场景2: false
场景3: false
```

## 三、解释器模式的高级用法

### 3.1 数学表达式解释器

```java
// ========== 抽象表达式 ==========
public interface MathExpression {
    double interpret();
}

// 数字
public class NumberExpression implements MathExpression {
    private final double value;
    public NumberExpression(double value) { this.value = value; }
    @Override public double interpret() { return value; }
    @Override public String toString() { return String.valueOf(value); }
}

// 加法
public class AddExpression implements MathExpression {
    private final MathExpression left;
    private final MathExpression right;
    public AddExpression(MathExpression left, MathExpression right) {
        this.left = left; this.right = right;
    }
    @Override public double interpret() { return left.interpret() + right.interpret(); }
    @Override public String toString() { return "(" + left + " + " + right + ")"; }
}

// 减法
public class SubtractExpression implements MathExpression {
    private final MathExpression left;
    private final MathExpression right;
    public SubtractExpression(MathExpression left, MathExpression right) {
        this.left = left; this.right = right;
    }
    @Override public double interpret() { return left.interpret() - right.interpret(); }
    @Override public String toString() { return "(" + left + " - " + right + ")"; }
}

// 乘法
public class MultiplyExpression implements MathExpression {
    private final MathExpression left;
    private final MathExpression right;
    public MultiplyExpression(MathExpression left, MathExpression right) {
        this.left = left; this.right = right;
    }
    @Override public double interpret() { return left.interpret() * right.interpret(); }
    @Override public String toString() { return "(" + left + " * " + right + ")"; }
}

// ========== 简易解析器 ==========
public class MathParser {
    // 解析 "(1 + 2) * 3" 这样的表达式
    public static MathExpression parse(String expression) {
        // 简化版：使用递归下降解析
        return new Parser(expression.trim()).parseExpression();
    }
    
    private static class Parser {
        private final String input;
        private int pos = 0;
        
        Parser(String input) { this.input = input; }
        
        MathExpression parseExpression() {
            MathExpression result = parseTerm();
            while (pos < input.length()) {
                char op = peek();
                if (op == '+') { consume(); result = new AddExpression(result, parseTerm()); }
                else if (op == '-') { consume(); result = new SubtractExpression(result, parseTerm()); }
                else break;
            }
            return result;
        }
        
        MathExpression parseTerm() {
            MathExpression result = parseFactor();
            while (pos < input.length()) {
                char op = peek();
                if (op == '*') { consume(); result = new MultiplyExpression(result, parseFactor()); }
                else break;
            }
            return result;
        }
        
        MathExpression parseFactor() {
            skipWhitespace();
            if (peek() == '(') {
                consume();  // (
                MathExpression expr = parseExpression();
                consume();  // )
                return expr;
            }
            return parseNumber();
        }
        
        MathExpression parseNumber() {
            skipWhitespace();
            StringBuilder sb = new StringBuilder();
            while (pos < input.length() && (Character.isDigit(input.charAt(pos)) || input.charAt(pos) == '.')) {
                sb.append(input.charAt(pos++));
            }
            return new NumberExpression(Double.parseDouble(sb.toString()));
        }
        
        char peek() { skipWhitespace(); return pos < input.length() ? input.charAt(pos) : '\0'; }
        void consume() { pos++; }
        void skipWhitespace() { while (pos < input.length() && Character.isWhitespace(input.charAt(pos))) pos++; }
    }
}

// 使用
MathExpression expr = MathParser.parse("(1 + 2) * 3");
System.out.println(expr + " = " + expr.interpret());  // (1.0 + 2.0) * 3.0 = 9.0
```

### 3.2 规则引擎解释器

```java
// 实现业务规则：price > 100 AND category == "electronics"
public interface RuleExpression {
    boolean evaluate(Map<String, Object> facts);
}

public class ComparisonExpression implements RuleExpression {
    private final String field;
    private final String operator;
    private final Object value;
    
    public ComparisonExpression(String field, String operator, Object value) {
        this.field = field; this.operator = operator; this.value = value;
    }
    
    @Override
    @SuppressWarnings("unchecked")
    public boolean evaluate(Map<String, Object> facts) {
        Object factValue = facts.get(field);
        if (factValue == null) return false;
        
        switch (operator) {
            case ">": return ((Comparable) factValue).compareTo(value) > 0;
            case "<": return ((Comparable) factValue).compareTo(value) < 0;
            case "==": return factValue.equals(value);
            case "!=": return !factValue.equals(value);
            default: throw new IllegalArgumentException("未知运算符: " + operator);
        }
    }
    
    @Override
    public String toString() { return field + " " + operator + " " + value; }
}

public class AndRule implements RuleExpression {
    private final RuleExpression left, right;
    public AndRule(RuleExpression left, RuleExpression right) { this.left = left; this.right = right; }
    @Override public boolean evaluate(Map<String, Object> facts) { return left.evaluate(facts) && right.evaluate(facts); }
}

public class OrRule implements RuleExpression {
    private final RuleExpression left, right;
    public OrRule(RuleExpression left, RuleExpression right) { this.left = left; this.right = right; }
    @Override public boolean evaluate(Map<String, Object> facts) { return left.evaluate(facts) || right.evaluate(facts); }
}

// 使用
RuleExpression rule = new AndRule(
    new ComparisonExpression("price", ">", 100),
    new ComparisonExpression("category", "==", "electronics")
);

Map<String, Object> product = Map.of("price", 299, "category", "electronics");
System.out.println("规则匹配: " + rule.evaluate(product));  // true
```

## 四、解释器模式在 JDK 中的应用

### 4.1 java.util.regex.Pattern

正则表达式引擎是解释器模式的经典应用：

```java
// 正则表达式引擎解释模式
Pattern pattern = Pattern.compile("a*b");  // 文法规则
Matcher matcher = pattern.matcher("aaaab");  // 输入
boolean matches = matcher.matches();  // 解释/匹配
```

### 4.2 java.text.Format

格式化类可以看作解释器：

```java
SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd");  // 文法
Date date = sdf.parse("2026-04-22");  // 解释
String formatted = sdf.format(date);  // 反向解释
```

### 4.3 EL 表达式

JSP/JSF 的 EL 表达式也是解释器：

```java
// #{user.name} → 解释为 getUser().getName()
```

## 五、解释器模式 vs 其他模式

### 5.1 对比组合模式

解释器模式通常基于组合模式来构建语法树。组合模式提供递归结构，解释器模式为组合结构添加解释语义。

### 5.2 对比访问者模式

| 维度 | 解释器模式 | 访问者模式 |
|------|---------|-----------|
| 目的 | 解释/执行表达式 | 对结构执行操作 |
| 结构 | 语法树 | 任意对象结构 |
| 扩展 | 新增文法规则 | 新增操作 |

## 六、解释器模式的优缺点

### 优点

1. **易于扩展文法**：新增文法规则只需新增类
2. **直观映射**：文法规则与类一一对应
3. **易于实现**：简单的文法容易实现

### 缺点

1. **复杂文法难维护**：文法复杂时类数量爆炸
2. **性能问题**：递归解释效率低
3. **实用性有限**：复杂解析通常用工具（ANTLR）

### 适用场景

- 需要解释执行特定领域语言
- 文法相对简单
- 需要快速原型实现 DSL
- 规则引擎、查询解析

## 七、面试常见问题

### Q1: 解释器模式的核心思想是什么？

解释器模式将文法规则映射为类，每条文法规则对应一个类。通过组合这些类构建语法树，然后递归解释执行。本质是用面向对象的方式实现语言的解释器。

### Q2: 解释器模式适合什么场景？

适合需要解释执行特定领域语言（DSL）的场景，且文法相对简单。典型应用：布尔表达式求值、规则引擎、简单查询语言。复杂文法建议使用 ANTLR 等工具。

### Q3: 解释器模式和组合模式有什么关系？

解释器模式通常使用组合模式来构建语法树——终结符是叶子节点，非终结符是组合节点。解释器在组合结构的基础上添加 interpret 语义。

### Q4: 为什么实际项目中很少用解释器模式？

因为对于复杂的文法，手写解释器类太多、性能差、维护难。实际项目中通常使用解析器生成工具（如 ANTLR、JavaCC）来自动生成解析代码。解释器模式更适合文法简单的场景。

## 八、总结

解释器模式是将文法规则映射为类的模式，它在简单 DSL 场景下非常优雅，但在复杂场景下通常被解析器生成工具替代。

**核心要点**：

1. **文法即类**：每条文法规则对应一个类
2. **递归解释**：语法树的递归遍历和解释
3. **终结符/非终结符**：叶子节点和组合节点
4. **适用简单文法**：复杂文法用工具生成
5. **实际应用**：正则表达式、规则引擎、简单 DSL

解释器模式告诉我们：有时候最好的编程方式就是创造一种语言来描述问题。

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
- [Java设计模式（二十）：备忘录模式深度实践](/posts/java设计模式二十-备忘录模式深度实践/)
- [Java设计模式（二十一）：状态模式深度实践](/posts/java设计模式二十一-状态模式深度实践/)
