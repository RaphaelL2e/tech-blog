---
title: "Java设计模式（八）：策略模式深度实践"
date: 2026-04-20T11:00:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "策略模式", "strategy"]
---

## 前言

前七篇文章我们介绍了创建型模式和部分结构型/行为型模式。今天继续 Java 设计模式系列，**策略模式（Strategy Pattern）** 是行为型模式中的核心成员，完美诠释了"面向接口编程"和"开闭原则"。

**核心思想**：定义一系列算法，把它们一个个封装起来，并且使它们可以相互替换。

<!--more-->

## 一、为什么需要策略模式

### 1.1 if-else 的噩梦

```java
// ❌ 典型的 if-else 代码
public class OrderService {
    
    public double calculateDiscount(Order order) {
        // 会员等级折扣
        if ("GOLD".equals(order.getMemberLevel())) {
            return order.getAmount() * 0.8;  // 金卡 8 折
        } else if ("SILVER".equals(order.getMemberLevel())) {
            return order.getAmount() * 0.9;  // 银卡 9 折
        } else if ("BRONZE".equals(order.getMemberLevel())) {
            return order.getAmount() * 0.95;  // 铜卡 9.5 折
        } else if ("NEWBIE".equals(order.getMemberLevel())) {
            return order.getAmount() * 0.98;  // 新人 9.8 折
        } else if ("BIRTHDAY".equals(order.getMemberType())) {
            return order.getAmount() * 0.7;   // 生日特惠 7 折
        } else if ("HOLIDAY".equals(order.getPromotionType())) {
            return order.getAmount() * 0.75; // 节日促销 7.5 折
        } else if ("FLASH".equals(order.getPromotionType())) {
            return order.getAmount() * 0.5;  // 闪购 5 折
        } else {
            return order.getAmount();  // 无折扣
        }
    }
    
    public String getDeliveryMethod(Order order) {
        // 配送方式选择
        if (order.getWeight() > 30) {
            return "LARGE_DELIVERY";  // 大件配送
        } else if (order.getWeight() > 10) {
            return "EXPRESS_DELIVERY";  // 快递
        } else if (order.getDistance() < 5) {
            return "SAME_DAY_DELIVERY";  // 同城当日达
        } else if (order.getIsUrgent()) {
            return "NEXT_DAY_DELIVERY";  // 次日达
        } else {
            return "STANDARD_DELIVERY";  // 标准配送
        }
    }
}
```

**问题**：
- 代码膨胀：每增加一种策略都要改这个类
- 违反开闭原则：必须修改现有代码
- 难以测试：所有逻辑混在一起
- 无法复用：折扣和配送逻辑强耦合

### 1.2 策略模式的优势

```java
// ✅ 使用策略模式
public class OrderService {
    
    private Map<String, DiscountStrategy> discountStrategies;
    private Map<String, DeliveryStrategy> deliveryStrategies;
    
    public double calculateDiscount(Order order) {
        DiscountStrategy strategy = discountStrategies.get(
            getDiscountKey(order));
        return strategy.calculate(order);
    }
    
    public String getDeliveryMethod(Order order) {
        DeliveryStrategy strategy = deliveryStrategies.get(
            getDeliveryKey(order));
        return strategy.deliver(order);
    }
}
```

**优点**：
- 消除 if-else
- 每个策略独立封装
- 新增策略无需修改现有代码
- 方便单元测试

## 二、策略模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                 Context (上下文/环境类)                      │
├─────────────────────────────────────────────────────────────┤
│ - strategy: Strategy                                        │
│ + setStrategy(Strategy)                                    │
│ + execute() → 委托给 strategy                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Strategy (抽象策略接口)                      │
├─────────────────────────────────────────────────────────────┤
│ + algorithmInterface()                                     │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴────────────────┐
▼                             ▼
┌─────────────┐        ┌─────────────┐
│ ConcreteStrA│        │ ConcreteStrB│
├─────────────┤        ├─────────────┤
│ +algorithm()│        │ +algorithm()│
└─────────────┘        └─────────────┘
```

### 2.2 完整代码实现

```java
// 抽象策略接口
public interface PayStrategy {
    
    /**
     * 支付
     * @param order 订单
     * @return 是否支付成功
     */
    boolean pay(Order order);
    
    /**
     * 退款
     * @param order 订单
     * @return 是否退款成功
     */
    boolean refund(Order order);
}

// 具体策略：支付宝
public class AlipayStrategy implements PayStrategy {
    
    @Override
    public boolean pay(Order order) {
        System.out.println("支付宝支付：" + order.getAmount());
        // 调用支付宝 SDK
        return true;
    }
    
    @Override
    public boolean refund(Order order) {
        System.out.println("支付宝退款：" + order.getAmount());
        // 调用支付宝退款 API
        return true;
    }
}

// 具体策略：微信支付
public class WechatPayStrategy implements PayStrategy {
    
    @Override
    public boolean pay(Order order) {
        System.out.println("微信支付：" + order.getAmount());
        // 调用微信支付 SDK
        return true;
    }
    
    @Override
    public boolean refund(Order order) {
        System.out.println("微信退款：" + order.getAmount());
        // 调用微信退款 API
        return true;
    }
}

// 具体策略：银联支付
public class UnionPayStrategy implements PayStrategy {
    
    @Override
    public boolean pay(Order order) {
        System.out.println("银联支付：" + order.getAmount());
        // 调用银联 SDK
        return true;
    }
    
    @Override
    public boolean refund(Order order) {
        System.out.println("银联退款：" + order.getAmount());
        return true;
    }
}

// 具体策略：信用卡支付
public class CreditCardStrategy implements PayStrategy {
    
    private String cardNumber;
    private String cvv;
    
    public CreditCardStrategy(String cardNumber, String cvv) {
        this.cardNumber = cardNumber;
        this.cvv = cvv;
    }
    
    @Override
    public boolean pay(Order order) {
        System.out.println("信用卡支付：" + order.getAmount() + 
            "，卡号：" + maskCard(cardNumber));
        return true;
    }
    
    @Override
    public boolean refund(Order order) {
        System.out.println("信用卡退款：" + order.getAmount());
        return true;
    }
    
    private String maskCard(String card) {
        return card.substring(0, 4) + "****" + card.substring(card.length() - 4);
    }
}

// 上下文类
public class OrderContext {
    
    private PayStrategy strategy;
    
    public void setStrategy(PayStrategy strategy) {
        this.strategy = strategy;
    }
    
    public boolean pay(Order order) {
        return strategy.pay(order);
    }
    
    public boolean refund(Order order) {
        return strategy.refund(order);
    }
}

// 订单类
public class Order {
    private String orderId;
    private double amount;
    private String payMethod;
    
    // constructors, getters, setters...
    public String getOrderId() { return orderId; }
    public double getAmount() { return amount; }
    public String getPayMethod() { return payMethod; }
}

// 客户端
public class StrategyTest {
    public static void main(String[] args) {
        OrderContext context = new OrderContext();
        Order order = new Order("ORD001", 199.99, "ALIPAY");
        
        // 策略 A
        context.setStrategy(new AlipayStrategy());
        context.pay(order);
        
        // 策略 B - 运行时切换
        context.setStrategy(new WechatPayStrategy());
        context.pay(order);
        
        // 策略 C - 带参数
        context.setStrategy(new CreditCardStrategy("6225881234567890", "123"));
        context.pay(order);
    }
}
```

## 三、策略模式实战案例

### 3.1 订单支付系统

```java
// 策略工厂 + 策略注册
public class PayStrategyFactory {
    
    private static final Map<String, PayStrategy> strategies = new HashMap<>();
    
    static {
        strategies.put("ALIPAY", new AlipayStrategy());
        strategies.put("WECHAT", new WechatPayStrategy());
        strategies.put("UNION", new UnionPayStrategy());
        strategies.put("CREDIT_CARD", new CreditCardStrategy("", ""));
    }
    
    public static PayStrategy getStrategy(String payType) {
        PayStrategy strategy = strategies.get(payType);
        if (strategy == null) {
            throw new IllegalArgumentException("不支持的支付方式：" + payType);
        }
        return strategy;
    }
    
    // 支持动态注册
    public static void register(String payType, PayStrategy strategy) {
        strategies.put(payType, strategy);
    }
}

// 订单服务
public class OrderService {
    
    public boolean pay(Order order) {
        PayStrategy strategy = PayStrategyFactory.getStrategy(
            order.getPayMethod());
        return strategy.pay(order);
    }
    
    public boolean refund(Order order) {
        PayStrategy strategy = PayStrategyFactory.getStrategy(
            order.getPayMethod());
        return strategy.refund(order);
    }
}
```

### 3.2 会员折扣系统

```java
// 折扣策略接口
public interface DiscountStrategy {
    
    /**
     * 计算折后价格
     * @param originalPrice 原价
     * @param order 订单（可获取更多上下文）
     * @return 折后价格
     */
    double calculate(double originalPrice, Order order);
    
    /**
     * 获取折扣名称
     */
    String getName();
}

// 金卡会员折扣
public class GoldMemberDiscount implements DiscountStrategy {
    
    @Override
    public double calculate(double originalPrice, Order order) {
        return originalPrice * 0.8;  // 8 折
    }
    
    @Override
    public String getName() {
        return "金卡会员折扣";
    }
}

// 银卡会员折扣
public class SilverMemberDiscount implements DiscountStrategy {
    
    @Override
    public double calculate(double originalPrice, Order order) {
        return originalPrice * 0.9;  // 9 折
    }
    
    @Override
    public String getName() {
        return "银卡会员折扣";
    }
}

// 生日特惠折扣
public class BirthdayDiscount implements DiscountStrategy {
    
    @Override
    public double calculate(double originalPrice, Order order) {
        return originalPrice * 0.7;  // 7 折
    }
    
    @Override
    public String getName() {
        return "生日特惠";
    }
}

// 节日促销折扣
public class HolidayDiscount implements DiscountStrategy {
    
    private double discountRate;
    
    public HolidayDiscount(double discountRate) {
        this.discountRate = discountRate;
    }
    
    @Override
    public double calculate(double originalPrice, Order order) {
        return originalPrice * discountRate;
    }
    
    @Override
    public String getName() {
        return "节日促销";
    }
}

// 满减折扣
public class FullReductionDiscount implements DiscountStrategy {
    
    private double threshold;  // 满 threshold
    private double reduction;  // 减 reduction
    
    public FullReductionDiscount(double threshold, double reduction) {
        this.threshold = threshold;
        this.reduction = reduction;
    }
    
    @Override
    public double calculate(double originalPrice, Order order) {
        if (originalPrice >= threshold) {
            return originalPrice - reduction;
        }
        return originalPrice;
    }
    
    @Override
    public String getName() {
        return String.format("满%.0f减%.0f", threshold, reduction);
    }
}

// 折扣策略上下文
public class DiscountContext {
    
    private DiscountStrategy strategy;
    
    public void setStrategy(DiscountStrategy strategy) {
        this.strategy = strategy;
    }
    
    public DiscountStrategy getStrategy() {
        return strategy;
    }
    
    public double calculate(double originalPrice, Order order) {
        return strategy.calculate(originalPrice, order);
    }
}

// 折扣计算服务
public class DiscountService {
    
    private final Map<String, DiscountStrategy> strategies = new HashMap<>();
    
    public DiscountService() {
        // 注册所有折扣策略
        strategies.put("GOLD", new GoldMemberDiscount());
        strategies.put("SILVER", new SilverMemberDiscount());
        strategies.put("BIRTHDAY", new BirthdayDiscount());
        strategies.put("FULL_100_10", new FullReductionDiscount(100, 10));
        strategies.put("FULL_200_30", new FullReductionDiscount(200, 30));
        strategies.put("FULL_500_100", new FullReductionDiscount(500, 100));
    }
    
    public DiscountStrategy getStrategy(Order order) {
        // 规则：优先使用生日折扣
        if (order.isBirthday()) {
            return strategies.get("BIRTHDAY");
        }
        
        // 其次使用会员折扣
        String memberLevel = order.getMemberLevel();
        DiscountStrategy memberStrategy = strategies.get(memberLevel);
        if (memberStrategy != null) {
            return memberStrategy;
        }
        
        // 最后检查满减
        double amount = order.getAmount();
        if (amount >= 500) {
            return strategies.get("FULL_500_100");
        } else if (amount >= 200) {
            return strategies.get("FULL_200_30");
        } else if (amount >= 100) {
            return strategies.get("FULL_100_10");
        }
        
        // 默认无折扣
        return price -> price;
    }
    
    public double calculateDiscount(Order order) {
        DiscountStrategy strategy = getStrategy(order);
        double originalPrice = order.getAmount();
        double discountedPrice = strategy.calculate(originalPrice, order);
        
        System.out.printf("原价：%.2f，折扣方式：%s，折后价：%.2f%n",
            originalPrice, strategy.getName(), discountedPrice);
        
        return originalPrice - discountedPrice;
    }
}

// 测试
public class DiscountTest {
    public static void main(String[] args) {
        DiscountService service = new DiscountService();
        
        Order order1 = new Order();
        order1.setAmount(299.0);
        order1.setMemberLevel("GOLD");
        service.calculateDiscount(order1);
        // 输出：原价：299.00，折扣方式：金卡会员折扣，折后价：239.20
        
        Order order2 = new Order();
        order2.setAmount(299.0);
        order2.setMemberLevel("GOLD");
        order2.setBirthday(true);  // 生日优先
        service.calculateDiscount(order2);
        // 输出：原价：299.00，折扣方式：生日特惠，折后价：209.30
        
        Order order3 = new Order();
        order3.setAmount(550.0);
        order3.setMemberLevel("SILVER");
        service.calculateDiscount(order3);
        // 输出：原价：550.00，折扣方式：满500减100，折后价：450.00
    }
}
```

### 3.3 排序策略

```java
// 排序策略接口
public interface SortStrategy<T> {
    
    /**
     * 排序
     * @param list 待排序列表
     * @return 排序后的列表
     */
    List<T> sort(List<T> list);
    
    /**
     * 策略名称
     */
    String getName();
}

// 快速排序
public class QuickSort<T extends Comparable<T>> implements SortStrategy<T> {
    
    @Override
    public List<T> sort(List<T> list) {
        if (list == null || list.size() <= 1) {
            return new ArrayList<>(list);
        }
        
        List<T> result = new ArrayList<>(list);
        quickSort(result, 0, result.size() - 1);
        return result;
    }
    
    private void quickSort(List<T> list, int low, int high) {
        if (low < high) {
            int pivot = partition(list, low, high);
            quickSort(list, low, pivot - 1);
            quickSort(list, pivot + 1, high);
        }
    }
    
    private int partition(List<T> list, int low, int high) {
        T pivot = list.get(high);
        int i = low - 1;
        for (int j = low; j < high; j++) {
            if (list.get(j).compareTo(pivot) <= 0) {
                i++;
                Collections.swap(list, i, j);
            }
        }
        Collections.swap(list, i + 1, high);
        return i + 1;
    }
    
    @Override
    public String getName() {
        return "快速排序";
    }
}

// 归并排序
public class MergeSort<T extends Comparable<T>> implements SortStrategy<T> {
    
    @Override
    public List<T> sort(List<T> list) {
        if (list == null || list.size() <= 1) {
            return new ArrayList<>(list);
        }
        
        List<T> result = new ArrayList<>(list);
        mergeSort(result, 0, result.size() - 1);
        return result;
    }
    
    private void mergeSort(List<T> list, int left, int right) {
        if (left < right) {
            int mid = (left + right) / 2;
            mergeSort(list, left, mid);
            mergeSort(list, mid + 1, right);
            merge(list, left, mid, right);
        }
    }
    
    @SuppressWarnings("unchecked")
    private void merge(List<T> list, int left, int mid, int right) {
        List<T> temp = new ArrayList<>();
        int i = left, j = mid + 1;
        
        while (i <= mid && j <= right) {
            if (list.get(i).compareTo(list.get(j)) <= 0) {
                temp.add(list.get(i++));
            } else {
                temp.add(list.get(j++));
            }
        }
        
        while (i <= mid) temp.add(list.get(i++));
        while (j <= right) temp.add(list.get(j++));
        
        for (int k = 0; k < temp.size(); k++) {
            list.set(left + k, temp.get(k));
        }
    }
    
    @Override
    public String getName() {
        return "归并排序";
    }
}

// 桶排序（适用于整数）
public class BucketSort implements SortStrategy<Integer> {
    
    @Override
    public List<Integer> sort(List<Integer> list) {
        if (list == null || list.size() <= 1) {
            return new ArrayList<>(list);
        }
        
        int max = Collections.max(list);
        int min = Collections.min(list);
        int bucketCount = (max - min) / list.size() + 1;
        
        List<List<Integer>> buckets = new ArrayList<>(bucketCount);
        for (int i = 0; i < bucketCount; i++) {
            buckets.add(new ArrayList<>());
        }
        
        // 分配到桶
        for (int num : list) {
            int index = (num - min) / list.size();
            buckets.get(index).add(num);
        }
        
        // 桶内排序
        for (List<Integer> bucket : buckets) {
            Collections.sort(bucket);
        }
        
        // 合并
        List<Integer> result = new ArrayList<>();
        for (List<Integer> bucket : buckets) {
            result.addAll(bucket);
        }
        return result;
    }
    
    @Override
    public String getName() {
        return "桶排序";
    }
}

// 排序上下文
public class Sorter<T> {
    
    private SortStrategy<T> strategy;
    
    public void setStrategy(SortStrategy<T> strategy) {
        this.strategy = strategy;
    }
    
    public List<T> sort(List<T> list) {
        System.out.println("使用策略：" + strategy.getName());
        return strategy.sort(list);
    }
}

// 智能排序器：根据数据特点自动选择策略
public class SmartSorter<T extends Comparable<T>> {
    
    public List<T> sort(List<T> list) {
        if (list == null || list.size() <= 1) {
            return new ArrayList<>(list);
        }
        
        SortStrategy<T> strategy;
        
        if (list.size() < 100) {
            // 小数据量，使用快速排序
            strategy = new QuickSort<>();
        } else if (isIntegerList(list)) {
            // 整数列表，使用桶排序
            strategy = (SortStrategy<T>) new BucketSort();
        } else {
            // 大数据量，使用归并排序（稳定）
            strategy = new MergeSort<>();
        }
        
        return strategy.sort(list);
    }
    
    @SuppressWarnings("unchecked")
    private boolean isIntegerList(List<T> list) {
        return list.get(0) instanceof Integer;
    }
}
```

### 3.4 验证策略

```java
// 验证策略接口
public interface ValidationStrategy<T> {
    
    /**
     * 验证是否通过
     * @param t 待验证对象
     * @return 是否通过
     */
    boolean validate(T t);
    
    /**
     * 获取错误消息
     */
    String getErrorMessage();
}

// 手机号验证
public class PhoneValidation implements ValidationStrategy<String> {
    
    private static final Pattern PHONE_PATTERN = 
        Pattern.compile("^1[3-9]\\d{9}$");
    
    @Override
    public boolean validate(String phone) {
        return PHONE_PATTERN.matcher(phone).matches();
    }
    
    @Override
    public String getErrorMessage() {
        return "手机号格式不正确";
    }
}

// 邮箱验证
public class EmailValidation implements ValidationStrategy<String> {
    
    private static final Pattern EMAIL_PATTERN = 
        Pattern.compile("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$");
    
    @Override
    public boolean validate(String email) {
        return EMAIL_PATTERN.matcher(email).matches();
    }
    
    @Override
    public String getErrorMessage() {
        return "邮箱格式不正确";
    }
}

// 密码强度验证
public class PasswordValidation implements ValidationStrategy<String> {
    
    private int minLength;
    private boolean requireUpperCase;
    private boolean requireLowerCase;
    private boolean requireDigit;
    private boolean requireSpecial;
    
    public PasswordValidation(int minLength, boolean requireUpperCase,
            boolean requireLowerCase, boolean requireDigit, boolean requireSpecial) {
        this.minLength = minLength;
        this.requireUpperCase = requireUpperCase;
        this.requireLowerCase = requireLowerCase;
        this.requireDigit = requireDigit;
        this.requireSpecial = requireSpecial;
    }
    
    @Override
    public boolean validate(String password) {
        if (password == null || password.length() < minLength) {
            return false;
        }
        
        boolean hasUpper = !requireUpperCase || password.matches(".*[A-Z].*");
        boolean hasLower = !requireLowerCase || password.matches(".*[a-z].*");
        boolean hasDigit = !requireDigit || password.matches(".*\\d.*");
        boolean hasSpecial = !requireSpecial || password.matches(".*[!@#$%^&*()].*");
        
        return hasUpper && hasLower && hasDigit && hasSpecial;
    }
    
    @Override
    public String getErrorMessage() {
        return String.format("密码长度至少%d位，需包含%s", 
            minLength,
            buildRequirement());
    }
    
    private String buildRequirement() {
        List<String> reqs = new ArrayList<>();
        if (requireUpperCase) reqs.add("大写字母");
        if (requireLowerCase) reqs.add("小写字母");
        if (requireDigit) reqs.add("数字");
        if (requireSpecial) reqs.add("特殊字符");
        return String.join("、", reqs);
    }
}

// 验证器上下文
public class Validator<T> {
    
    private List<ValidationStrategy<T>> strategies = new ArrayList<>();
    
    public Validator<T> addStrategy(ValidationStrategy<T> strategy) {
        strategies.add(strategy);
        return this;
    }
    
    public ValidationResult validate(T t) {
        List<String> errors = new ArrayList<>();
        
        for (ValidationStrategy<T> strategy : strategies) {
            if (!strategy.validate(t)) {
                errors.add(strategy.getErrorMessage());
            }
        }
        
        return new ValidationResult(errors.isEmpty(), errors);
    }
    
    public static class ValidationResult {
        private final boolean valid;
        private final List<String> errors;
        
        public ValidationResult(boolean valid, List<String> errors) {
            this.valid = valid;
            this.errors = errors;
        }
        
        public boolean isValid() { return valid; }
        public List<String> getErrors() { return errors; }
        public String getErrorMessage() { return String.join("; ", errors); }
    }
}

// 使用
public class ValidationTest {
    public static void main(String[] args) {
        // 手机号 + 邮箱验证
        Validator<String> contactValidator = new Validator<String>()
            .addStrategy(new PhoneValidation())
            .addStrategy(new EmailValidation());
        
        ValidationResult r1 = contactValidator.validate("13812345678");
        System.out.println("13812345678: " + (r1.isValid() ? "通过" : r1.getErrorMessage()));
        
        ValidationResult r2 = contactValidator.validate("invalid@email");
        System.out.println("invalid@email: " + (r2.isValid() ? "通过" : r2.getErrorMessage()));
        
        // 密码验证
        Validator<String> passwordValidator = new Validator<String>()
            .addStrategy(new PasswordValidation(8, true, true, true, true));
        
        ValidationResult r3 = passwordValidator.validate("Pass123!");
        System.out.println("Pass123!: " + (r3.isValid() ? "通过" : r3.getErrorMessage()));
        
        ValidationResult r4 = passwordValidator.validate("weak");
        System.out.println("weak: " + (r4.isValid() ? "通过" : r4.getErrorMessage()));
    }
}
```

## 四、策略模式 + 工厂模式

### 4.1 策略工厂

```java
// 策略注册表 + 工厂
public class StrategyRegistry<T, R> {
    
    private final Map<T, Supplier<R>> registry = new HashMap<>();
    
    public StrategyRegistry<T, R> register(T key, Supplier<R> supplier) {
        registry.put(key, supplier);
        return this;
    }
    
    public R get(T key) {
        Supplier<R> supplier = registry.get(key);
        if (supplier == null) {
            throw new IllegalArgumentException("未找到策略: " + key);
        }
        return supplier.get();
    }
    
    public Optional<R> getOptional(T key) {
        Supplier<R> supplier = registry.get(key);
        return supplier != null ? Optional.of(supplier.get()) : Optional.empty();
    }
    
    public boolean contains(T key) {
        return registry.containsKey(key);
    }
}

// 支付策略工厂
public class PayStrategyFactory2 {
    
    private static final StrategyRegistry<String, PayStrategy> REGISTRY = 
        new StrategyRegistry<>();
    
    static {
        REGISTRY.register("ALIPAY", AlipayStrategy::new);
        REGISTRY.register("WECHAT", WechatPayStrategy::new);
        REGISTRY.register("UNION", UnionPayStrategy::new);
        REGISTRY.register("CREDIT_CARD", () -> new CreditCardStrategy("", ""));
    }
    
    public static PayStrategy getStrategy(String payType) {
        return REGISTRY.get(payType);
    }
    
    public static void register(String payType, Supplier<PayStrategy> supplier) {
        REGISTRY.register(payType, supplier);
    }
}
```

### 4.2 Spring 集成

```java
// 策略注册为 Spring Bean
@Component
public class PayStrategyFactory3 {
    
    private final Map<String, PayStrategy> strategyMap = new HashMap<>();
    
    @Autowired
    public PayStrategyFactory3(List<PayStrategy> strategies) {
        for (PayStrategy strategy : strategies) {
            // 根据类名注册
            String name = strategy.getClass().getSimpleName()
                .replace("Strategy", "")
                .toUpperCase();
            strategyMap.put(name, strategy);
        }
    }
    
    public PayStrategy getStrategy(String payType) {
        PayStrategy strategy = strategyMap.get(payType.toUpperCase());
        if (strategy == null) {
            throw new IllegalArgumentException("不支持的支付方式: " + payType);
        }
        return strategy;
    }
}

// 使用 @Primary 标记默认策略
@Component
@Primary
public class DefaultPayStrategy implements PayStrategy {
    // 默认实现
}

// 使用 @Order 控制优先级
@Component
@Order(1)
public class HighPriorityPayStrategy implements PayStrategy {
    // 高优先级策略
}
```

## 五、策略模式 vs 其他模式

### 5.1 对比

| 维度 | 策略模式 | 状态模式 | 工厂模式 | 命令模式 |
|------|---------|---------|---------|---------|
| **目的** | 算法替换 | 状态转换 | 对象创建 | 请求封装 |
| **关注点** | 行为算法 | 对象状态 | 创建过程 | 操作封装 |
| **调用方式** | 上下文调用 | 状态对象调用 | 工厂返回 | 执行者调用 |
| **状态保存** | 无 | 有 | 无 | 有 |

### 5.2 策略 vs 简单工厂

```java
// 简单工厂：创建对象
public class PayFactory {
    public static PayStrategy create(String type) {
        if ("ALIPAY".equals(type)) {
            return new AlipayStrategy();
        } else if ("WECHAT".equals(type)) {
            return new WechatPayStrategy();
        }
        throw new IllegalArgumentException();
    }
}

// 策略模式：使用对象
public class OrderService {
    public void pay(Order order) {
        PayStrategy strategy = PayFactory.create(order.getPayMethod());
        strategy.pay(order);
    }
}

// 策略 + 工厂结合
public class OrderService2 {
    private PayStrategyFactory factory;
    
    public void pay(Order order) {
        PayStrategy strategy = factory.getStrategy(order.getPayType());
        strategy.pay(order);
    }
}
```

### 5.3 策略 vs 状态

```java
// 状态模式：对象根据内部状态改变行为
public class Order {
    private OrderState state;
    
    public void pay() {
        state.pay(this);  // 状态决定行为
    }
    
    public void deliver() {
        state.deliver(this);  // 状态转换
    }
}

public interface OrderState {
    void pay(Order order);
    void deliver(Order order);
    void complete(Order order);
}

// 策略模式：用户选择不同算法
public class Order2 {
    private PayStrategy payStrategy;
    
    public void setPayStrategy(PayStrategy strategy) {
        this.payStrategy = strategy;
    }
    
    public void pay() {
        payStrategy.pay(this);  // 策略决定行为
    }
}
```

**核心区别**：
- **状态模式**：状态转换是自动的（内部触发）
- **策略模式**：策略选择是外部的（用户指定）

## 六、策略模式的优缺点

### 6.1 优点

1. **消除 if-else**：代码更简洁
2. **开闭原则**：新增策略无需修改现有代码
3. **单一职责**：每个策略独立
4. **可测试**：策略可以单独测试
5. **运行时切换**：动态选择算法

### 6.2 缺点

1. **类数量增加**：每个策略一个类
2. **客户端需要知道所有策略**：需要选择正确的策略
3. **策略间可能重复**：策略类可能有重复代码

### 6.3 优化：策略抽象 + 模版方法

```java
// 抽象策略 + 模版方法
public abstract class AbstractDiscountStrategy implements DiscountStrategy {
    
    @Override
    public double calculate(double originalPrice, Order order) {
        // 模版方法：先校验，再计算
        if (!isApplicable(order)) {
            return originalPrice;
        }
        return doCalculate(originalPrice, order);
    }
    
    // 钩子方法：是否适用
    protected boolean isApplicable(Order order) {
        return true;
    }
    
    // 抽象方法：具体计算逻辑
    protected abstract double doCalculate(double originalPrice, Order order);
}

// 具体策略只需实现计算逻辑
public class MemberDiscount extends AbstractDiscountStrategy {
    
    private double rate;
    
    public MemberDiscount(double rate) {
        this.rate = rate;
    }
    
    @Override
    protected boolean isApplicable(Order order) {
        return order.getMemberLevel() != null;
    }
    
    @Override
    protected double doCalculate(double originalPrice, Order order) {
        return originalPrice * rate;
    }
}
```

## 七、源码中的应用

### 7.1 JDK 中的 Comparator

```java
// Comparator 就是策略模式
List<String> list = Arrays.asList("c", "a", "b");

// 策略1：自然顺序
list.sort(Comparator.naturalOrder());

// 策略2：反转顺序
list.sort(Comparator.reverseOrder());

// 策略3：自定义
list.sort(Comparator.comparing(String::length).thenComparing(String::compareTo));
```

### 7.2 Spring Security

```java
// 认证策略
public interface AuthenticationProvider {
    Authentication authenticate(Authentication authentication)
        throws AuthenticationException;
}

// 多种认证策略
public class DaoAuthenticationProvider implements AuthenticationProvider { }
public class JwtAuthenticationProvider implements AuthenticationProvider { }
public class OAuth2AuthenticationProvider implements AuthenticationProvider { }
```

### 7.3 Spring MVC 中的 HttpMessageConverter

```java
// 消息转换策略
public interface HttpMessageConverter<T> {
    boolean canRead(Class<?> clazz, MediaType mediaType);
    boolean canWrite(Class<?> clazz, MediaType mediaType);
    // ...
}

// JSON 转换策略
public class MappingJackson2HttpMessageConverter implements HttpMessageConverter { }
// XML 转换策略
public class Jaxb2RootElementHttpMessageConverter implements HttpMessageConverter { }
```

## 八、最佳实践

### 8.1 使用枚举简化

```java
// 枚举 + 策略
public enum PayType {
    ALIPAY {
        @Override
        public PayStrategy getStrategy() {
            return new AlipayStrategy();
        }
    },
    WECHAT {
        @Override
        public PayStrategy getStrategy() {
            return new WechatPayStrategy();
        }
    },
    UNION {
        @Override
        public PayStrategy getStrategy() {
            return new UnionPayStrategy();
        }
    };
    
    public abstract PayStrategy getStrategy();
}

// 使用
public class OrderService3 {
    public boolean pay(Order order) {
        PayStrategy strategy = order.getPayType().getStrategy();
        return strategy.pay(order);
    }
}
```

### 8.2 策略 + Lambda

```java
// JDK 内置策略
List<Integer> numbers = Arrays.asList(5, 2, 8, 1, 9);

// Lambda 作为策略
numbers.sort((a, b) -> b - a);  // 降序

// Comparator 作为策略
numbers.sort(Comparator.comparingInt(Integer::intValue).reversed());

// 复杂策略
numbers.sort(Comparator
    .comparingInt(n -> n % 2)      // 先按奇偶分
    .thenComparingInt(n -> n));   // 再按大小排
```

### 8.3 默认策略

```java
public class PayStrategyFactory4 {
    
    private static final Map<String, PayStrategy> strategies = new HashMap<>();
    private static final PayStrategy DEFAULT = new DefaultPayStrategy();
    
    static {
        strategies.put("ALIPAY", new AlipayStrategy());
        strategies.put("WECHAT", new WechatPayStrategy());
    }
    
    public static PayStrategy getStrategy(String payType) {
        return strategies.getOrDefault(payType, DEFAULT);
    }
}
```

## 九、面试常见问题

### Q1：策略模式和 if-else 的区别？

| 维度 | if-else | 策略模式 |
|------|---------|---------|
| 扩展性 | 差（改代码） | 好（新增策略类） |
| 可测试性 | 差（逻辑混在一起） | 好（独立测试） |
| 代码行数 | 膨胀 | 分散 |
| 违反原则 | 开闭原则 | 符合开闭原则 |

### Q2：策略模式和状态模式如何选择？

- **策略模式**：外部选择算法，不自动转换
- **状态模式**：内部状态自动转换，状态决定行为

### Q3：策略模式有什么缺点？如何优化？

- **缺点**：类数量增加，客户端需要知道所有策略
- **优化**：
  1. 使用工厂管理策略
  2. 使用枚举简化策略选择
  3. 结合 Spring 的依赖注入

### Q4：Spring 中哪些地方用到了策略模式？

1. **Resource**：不同资源访问策略
2. **ViewResolver**：视图解析策略
3. **MessageConverter**：消息转换策略
4. **AuthenticationProvider**：认证策略

## 十、总结

### 模式对比

```
行为型模式对比：
┌───────────┬─────────────────────────────────┐
│   模式    │ 目的                             │
├───────────┼─────────────────────────────────┤
│ 策略模式  │ 算法替换，外部选择                 │
│ 状态模式  │ 状态转换，内部自动切换             │
│ 命令模式  │ 请求封装为对象                     │
│ 观察者模式│ 一对多通知依赖                     │
│ 模板方法  │ 流程固定，步骤可变                 │
└───────────┴─────────────────────────────────┘
```

### 核心要点

1. **策略接口**：定义统一的行为
2. **具体策略**：封装具体算法
3. **上下文**：持有策略，委托执行
4. **工厂**：管理策略的创建和选择

## 结语

策略模式是消除 if-else 的利器，特别适合支付、折扣、排序等场景。掌握策略模式，能够设计出更灵活、更易扩展的系统。

**下期预告**：模板方法模式（Template Method Pattern）

> 记住：**策略是"用哪个"，状态是"变成什么"**。
