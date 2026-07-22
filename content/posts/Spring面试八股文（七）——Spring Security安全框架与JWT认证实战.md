---
title: Spring面试八股文（七）——Spring Security安全框架与JWT认证实战
date: 2026-07-10 10:00:00+08:00
updated: '2026-07-10T10:00:00+08:00'
description: 深入解析Spring Security安全框架的核心架构、认证授权机制、JWT令牌实现，以及微服务环境下的安全实践。结合面试高频考点，提供完整的实战代码示例。
topic: java-spring
series: spring-interview
series_order: 7
level: intermediate
status: maintained
tags:
- Java
- Spring
- Spring Security
- 面试八股文
categories:
- Java 与 Spring
draft: false
keywords:
- Spring Security
- JWT
- OAuth2
- 认证授权
- RBAC
- Spring Boot
---

## 一、核心架构概述

### 1.1 Spring Security是什么

Spring Security是Spring生态中最核心的安全框架，专注于为Java应用提供**认证（Authentication）**和**授权（Authorization）**两大核心能力。它并非Spring MVC专属，任何Java应用（包括传统Servlet应用、非Web应用）都可以集成Spring Security来实现安全控制。

从架构层面看，Spring Security采用了**过滤器链（Filter Chain）**的设计模式，所有的安全控制都通过一系列Filter进行拦截和处理。这种设计使得Spring Security可以在请求到达Controller之前就完成身份验证和权限校验，效率高且扩展性强。

**面试高频问题**：Spring Security的核心过滤器链有哪些？

Spring Security默认的过滤器链按顺序包括：

1. **ChannelProcessingFilter** — 处理HTTP/HTTPS协议切换
2. **SecurityContextPersistenceFilter** — 在Session中存取SecurityContext
3. **ConcurrentSessionFilter** — 并发会话控制
4. **UsernamePasswordAuthenticationFilter** — 表单登录认证（处理/login请求）
5. **BasicAuthenticationFilter** — HTTP Basic认证
6. **SecurityContextHolderAwareRequestFilter** — 包装HttpServletRequest
7. **RememberMeAuthenticationFilter** — "记住我"功能
8. **AnonymousAuthenticationFilter** — 为匿名用户创建匿名认证Token
9. **SessionManagementFilter** — Session管理
10. **ExceptionTranslationFilter** — 捕获安全异常并返回HTTP 401/403
11. **FilterSecurityInterceptor** — 最后的权限校验关卡

理解过滤器链顺序非常重要——它决定了认证授权的执行时机。比如你自定义了一个认证过滤器，必须正确配置其插入位置，才能在正确时机生效。

### 1.2 与其他安全方案的对比

在Java生态中，常见的认证授权方案有以下几种：

| 方案 | 特点 | 适用场景 |
|------|------|----------|
| Spring Security | 功能最全面，与Spring生态深度集成 | 企业级Spring应用 |
| Shiro | 轻量级，学习曲线平缓 | 中小型项目 |
| JWT + Filter | 无状态，跨语言友好 | 微服务、RESTful API |
| OAuth2 + SSO | 社交登录，单点登录 | 开放平台、生态系统 |
| Session + Cookie | 服务端会话，成熟稳定 | 传统Web应用 |

Spring Security的核心优势在于其**高度可扩展性**和**与Spring Boot的深度集成**。特别是Spring Boot Starter出现后，只需引入依赖即可自动配置完整的安全策略，开发效率大幅提升。

## 二、认证机制深度解析

### 2.1 认证流程全解析

Spring Security的认证流程是其最核心的机制，理解这个流程是掌握Spring Security的必经之路。

整个认证流程涉及以下核心组件：

**请求 → Security Filter Chain → AuthenticationManager → AuthenticationProvider → UserDetailsService → Authentication对象 → SecurityContext**

具体流程如下：

```
1. 用户提交用户名密码
2. UsernamePasswordAuthenticationFilter拦截请求，生成UsernamePasswordAuthenticationToken（未认证状态）
3. Token传递给AuthenticationManager
4. AuthenticationManager调用合适的AuthenticationProvider
5. AuthenticationProvider调用UserDetailsService.loadUserByUsername()加载用户信息
6. UserDetailsService根据用户名从数据库/内存中查询用户详情，返回UserDetails
7. AuthenticationProvider对比用户提交的密码和UserDetails中的密码（加密后比对）
8. 认证成功：创建已认证的Authentication，存入SecurityContext
9. 认证失败：抛出AuthenticationException
```

**面试高频问题**：请描述Spring Security的认证流程？

这是一道典型的Spring Security八股文题目。回答时需要涵盖以下关键点：过滤器链的入口作用、AuthenticationManager作为认证入口、AuthenticationProvider作为实际认证逻辑执行者、UserDetailsService加载用户数据、密码加密比对、以及SecurityContext的存储过程。

### 2.2 密码加密机制

Spring Security 5.x之后强制要求使用密码Encoder，且默认使用**BCryptPasswordEncoder**。BCrypt是一种基于Blowfish加密算法的哈希函数，具有内置盐值（salt），每次加密结果都不同，安全性极高。

```java
// BCrypt加密示例
@Test
public void testPasswordEncoding() {
    PasswordEncoder encoder = new BCryptPasswordEncoder();
    
    String rawPassword = "123456";
    String encodedPassword1 = encoder.encode(rawPassword);
    String encodedPassword2 = encoder.encode(rawPassword);
    
    // BCrypt每次加密结果不同（因为有随机盐）
    System.out.println("Encoded 1: " + encodedPassword1);
    System.out.println("Encoded 2: " + encodedPassword2);
    
    // 但matches()返回true
    System.out.println("Matches: " + encoder.matches(rawPassword, encodedPassword1));
}
```

**BCrypt为什么安全？**

- **自适应哈希**：BCrypt的强度因子（cost factor）可以调整，计算时间随因子指数增长，有效抵御暴力破解
- **内置盐值**：每个密码都有独立的随机盐，防止彩虹表攻击
- **不可逆**：哈希函数单项计算，无法从哈希值反推原始密码

**其他密码Encoder方案**：

```java
// SCrypt（更现代，但计算更慢）
PasswordEncoder scrypt = new SCryptPasswordEncoder();

// Argon2（目前最先进，但需要引入额外依赖）
PasswordEncoder argon2 = new Argon2PasswordEncoder();

// MD5/SHA-1（不推荐，仅用于兼容旧系统）
PasswordEncoder md5 = new MessageDigestPasswordEncoder("MD5");
PasswordEncoder sha1 = new MessageDigestPasswordEncoder("SHA-1");
```

### 2.3 内存认证与数据库认证

Spring Security支持多种用户信息来源：

**方式一：内存认证（适用于快速原型）**

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    
    @Bean
    public UserDetailsService userDetailsService() {
        InMemoryUserDetailsManager manager = new InMemoryUserDetailsManager();
        
        manager.createUser(User.withUsername("admin")
            .password("{noop}admin123")  // {noop}表示不加密，用于测试
            .roles("ADMIN", "USER")
            .authorities("ROLE_ADMIN", "ROLE_USER")
            .build());
            
        manager.createUser(User.withUsername("user")
            .password("{bcrypt}$2a$10$...")  // BCrypt加密密码
            .roles("USER")
            .build());
            
        return manager;
    }
}
```

**方式二：数据库认证（生产环境标准做法）**

```java
@Service
public class CustomUserDetailsService implements UserDetailsService {
    
    @Autowired
    private UserMapper userMapper;
    
    @Override
    public UserDetails loadUserByUsername(String username) 
            throws UsernameNotFoundException {
        
        // 从数据库查询用户
        User user = userMapper.findByUsername(username);
        if (user == null) {
            throw new UsernameNotFoundException("用户不存在: " + username);
        }
        
        // 转换为Spring Security的UserDetails
        return org.springframework.security.core.userdetails.User.builder()
            .username(user.getUsername())
            .password(user.getPassword())
            .roles(user.getRoles().toArray(new String[0]))
            .authorities(user.getPermissions().toArray(new String[0]))
            .accountExpired(user.isAccountExpired())
            .accountLocked(user.isAccountLocked())
            .credentialsExpired(user.isCredentialsExpired())
            .disabled(!user.isEnabled())
            .build();
    }
}
```

## 三、授权机制深度解析

### 3.1 权限模型：RBAC

Spring Security的授权基于**RBAC（Role-Based Access Control）**模型，即基于角色的访问控制。在RBAC中：

- **User（用户）** — 系统的实际使用者
- **Role（角色）** — 一组权限的集合，代表一种业务身份（如ADMIN、USER、MANAGER）
- **Permission（权限）** — 具体的操作许可（如READ、WRITE、DELETE）
- **User ↔ Role ↔ Permission** — 多对多关系

Spring Security同时支持**角色（Role）**和**权限（Authority）**两种粒度：

```java
// 角色以 ROLE_ 前缀区分，权限无前缀
// 建议：角色用 hasRole()，权限用 hasAuthority()
.authorities("ROLE_ADMIN", "user:read", "user:write", "user:delete")
```

### 3.2 Web层授权配置

Spring Security提供了简洁的链式API来配置URL级别的权限：

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)  // 前后端分离API禁用CSRF
            
            // 授权配置
            .authorizeHttpRequests(auth -> auth
                // 公开接口：无需认证
                .requestMatchers("/api/auth/login", "/api/auth/register", 
                                 "/api/public/**", "/error").permitAll()
                
                // 管理员专属接口
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                
                // 需要特定权限的接口
                .requestMatchers("/api/user/**").hasAnyRole("USER", "ADMIN")
                
                // 基于权限的细粒度控制
                .requestMatchers("/api/orders/**")
                    .hasAuthority("ORDER_READ")
                
                // 所有其他请求需要认证
                .anyRequest().authenticated()
            )
            
            // HTTP Basic认证配置
            .httpBasic(Customizer.withDefaults())
            
            // Session管理
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS)  // 无状态（JWT场景）
                .maximumSessions(1)  // 最多一个活跃会话
                .maxSessionsPreventsLogin(true)  // 禁止第二处登录
            )
            
            // 异常处理
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint((request, response, authException) -> {
                    response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                    response.setContentType("application/json");
                    response.getWriter().write("{\"error\": \"未登录\"}");
                })
                .accessDeniedHandler((request, response, accessDeniedException) -> {
                    response.setStatus(HttpServletResponse.SC_FORBIDDEN);
                    response.setContentType("application/json");
                    response.getWriter().write("{\"error\": \"权限不足\"}");
                })
            );
        
        return http.build();
    }
}
```

**面试高频问题**：hasRole()和hasAuthority()有什么区别？

两者的本质区别在于前缀处理。hasRole("ADMIN")会自动加上ROLE_前缀，变成检查hasAuthority("ROLE_ADMIN")；而hasAuthority("ADMIN")则精确匹配。Spring Security推荐用hasRole()检查角色，hasAuthority()检查具体权限。

### 3.3 方法级授权：@PreAuthorize

除了Web层，Spring Security还支持方法级别的权限控制：

```java
@Configuration
@EnableMethodSecurity(prePostEnabled = true)  // 启用方法级安全
public class SecurityConfig {
    // ...
}

// 在Service或Controller方法上使用
@Service
public class OrderService {
    
    @PreAuthorize("hasRole('ADMIN')")
    public void deleteOrder(Long orderId) {
        // 只有管理员可以删除订单
    }
    
    @PreAuthorize("hasAuthority('ORDER_READ') or hasRole('ADMIN')")
    public Order getOrder(Long orderId) {
        // 拥有ORDER_READ权限或ADMIN角色均可访问
        return orderRepository.findById(orderId);
    }
    
    // SpEL表达式实现复杂权限逻辑
    @PreAuthorize("#username == authentication.name or hasRole('ADMIN')")
    public UserProfile getUserProfile(String username) {
        // 用户只能查看自己的信息，或者管理员可以查看任意用户
    }
    
    @PreAuthorize("@customService.checkAccess(#orderId, authentication)")
    public Order updateOrder(Long orderId, Order order) {
        // 通过自定义Bean实现复杂权限判断
    }
}
```

## 四、JWT认证实战

### 4.1 为什么微服务选择JWT

在微服务架构中，传统的Session认证存在以下问题：

1. **分布式Session管理复杂**：Session需要共享到Redis等外部存储，增加了系统复杂度
2. **跨域问题**：微服务通常有多个独立域名，Cookie无法跨域传递
3. **扩展性差**：新增服务节点需要考虑Session路由
4. **性能开销**：每次请求都要查询Session存储

JWT（JSON Web Token）通过**无状态令牌**完美解决了这些问题：

- **无状态**：Token本身包含用户信息，服务器无需存储Session
- **自包含**：Token中携带了所有必要信息，验证只需解析Token
- **跨域友好**：通过Authorization Header传递，不受Cookie限制
- **可验证**：Token使用签名，无法伪造

### 4.2 JWT实现完整代码

**依赖引入**：

```xml
<dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-api</artifactId>
    <version>0.12.5</version>
</dependency>
<dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-impl</artifactId>
    <version>0.12.5</version>
    <scope>runtime</scope>
</dependency>
<dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-jackson</artifactId>
    <version>0.12.5</version>
    <scope>runtime</scope>
</dependency>
```

**JWT工具类**：

```java
@Component
public class JwtUtils {
    
    @Value("${jwt.secret:mySecretKeyForJWTTokenGenerationMustBeLongEnough}")
    private String secret;
    
    @Value("${jwt.expiration:86400000}")  // 24小时
    private long expiration;
    
    /**
     * 生成JWT Token
     * JWT由三部分组成：Header.Payload.Signature
     */
    public String generateToken(UserDetails userDetails) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("roles", userDetails.getAuthorities().stream()
            .map(GrantedAuthority::getAuthority)
            .collect(Collectors.toList()));
        claims.put("type", "access");
        
        return Jwts.builder()
            .claims(claims)
            .subject(userDetails.getUsername())
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + expiration))
            .signWith(Keys.hmacShaKeyFor(secret.getBytes()))
            .compact();
    }
    
    /**
     * 生成刷新Token（有效期更长）
     */
    public String generateRefreshToken(String username) {
        return Jwts.builder()
            .subject(username)
            .claim("type", "refresh")
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + expiration * 7))  // 7天
            .signWith(Keys.hmacShaKeyFor(secret.getBytes()))
            .compact();
    }
    
    /**
     * 解析Token，获取用户名
     */
    public String extractUsername(String token) {
        return extractClaims(token).getSubject();
    }
    
    /**
     * 提取所有Claims
     */
    public Claims extractClaims(String token) {
        return Jwts.parser()
            .verifyWith(Keys.hmacShaKeyFor(secret.getBytes()))
            .build()
            .parseSignedClaims(token)
            .getPayload();
    }
    
    /**
     * 验证Token是否有效
     */
    public boolean validateToken(String token, UserDetails userDetails) {
        try {
            final String username = extractUsername(token);
            // 检查用户名匹配且Token未过期
            return username.equals(userDetails.getUsername()) 
                && !isTokenExpired(token);
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }
    
    private boolean isTokenExpired(String token) {
        return extractClaims(token).getExpiration().before(new Date());
    }
}
```

**JWT认证过滤器**：

```java
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    
    @Autowired
    private JwtUtils jwtUtils;
    
    @Autowired
    private UserDetailsService userDetailsService;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request, 
                                    HttpServletResponse response, 
                                    FilterChain filterChain)
            throws ServletException, IOException {
        
        final String authHeader = request.getHeader("Authorization");
        
        // 提取JWT Token
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }
        
        final String jwt = authHeader.substring(7);
        
        try {
            // 解析Token获取用户名
            final String username = jwtUtils.extractUsername(jwt);
            
            // 如果能从Token中提取用户名，且当前SecurityContext无认证信息
            if (username != null && 
                SecurityContextHolder.getContext().getAuthentication() == null) {
                
                // 加载用户详情
                UserDetails userDetails = userDetailsService
                    .loadUserByUsername(username);
                
                // 验证Token有效性
                if (jwtUtils.validateToken(jwt, userDetails)) {
                    // 创建已认证的Token
                    UsernamePasswordAuthenticationToken authToken =
                        new UsernamePasswordAuthenticationToken(
                            userDetails,
                            null,
                            userDetails.getAuthorities()
                        );
                    
                    authToken.setDetails(
                        new WebAuthenticationDetailsSource()
                            .buildDetails(request)
                    );
                    
                    // 存入SecurityContext
                    SecurityContextHolder.getContext().setAuthentication(authToken);
                }
            }
        } catch (Exception e) {
            // Token无效，继续过滤器链（最终会被Spring Security拦截）
            log.error("JWT认证失败: {}", e.getMessage());
        }
        
        filterChain.doFilter(request, response);
    }
}
```

**SecurityConfig整合JWT**：

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {
    
    @Autowired
    private JwtAuthenticationFilter jwtAuthFilter;
    
    @Autowired
    private JwtAuthenticationEntryPoint jwtAuthEntryPoint;
    
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(session -> 
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**").permitAll()
                .anyRequest().authenticated()
            )
            
            // 将JWT过滤器插入UsernamePasswordAuthenticationFilter之前
            .addFilterBefore(jwtAuthFilter, 
                UsernamePasswordAuthenticationFilter.class)
            
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint(jwtAuthEntryPoint)
            );
        
        return http.build();
    }
}
```

**登录Controller**：

```java
@RestController
@RequestMapping("/api/auth")
public class AuthController {
    
    @Autowired
    private AuthenticationManager authenticationManager;
    
    @Autowired
    private JwtUtils jwtUtils;
    
    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        // 1. 使用Spring Security的AuthenticationManager进行认证
        Authentication authentication = authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(
                request.getUsername(),
                request.getPassword()
            )
        );
        
        // 2. 认证成功，生成Token
        UserDetails userDetails = (UserDetails) authentication.getPrincipal();
        String accessToken = jwtUtils.generateToken(userDetails);
        String refreshToken = jwtUtils.generateRefreshToken(userDetails.getUsername());
        
        return ResponseEntity.ok(AuthResponse.builder()
            .accessToken(accessToken)
            .refreshToken(refreshToken)
            .tokenType("Bearer")
            .expiresIn(86400)
            .username(userDetails.getUsername())
            .build());
    }
    
    @PostMapping("/refresh")
    public ResponseEntity<?> refresh(@RequestBody RefreshRequest request) {
        // 验证刷新Token，生成新的访问Token
        String username = jwtUtils.extractUsername(request.getRefreshToken());
        UserDetails userDetails = userDetailsService.loadUserByUsername(username);
        
        if (jwtUtils.validateToken(request.getRefreshToken(), userDetails)) {
            String newAccessToken = jwtUtils.generateToken(userDetails);
            return ResponseEntity.ok(AuthResponse.builder()
                .accessToken(newAccessToken)
                .tokenType("Bearer")
                .build());
        }
        
        return ResponseEntity.status(401).body("Refresh Token无效");
    }
}
```

### 4.3 JWT安全最佳实践

**面试高频问题**：JWT有什么安全隐患？如何防范？

这是JWT相关面试中最重要的问题之一。JWT的安全风险及应对措施如下：

| 安全风险 | 应对措施 |
|----------|----------|
| Token被窃取 | 使用HTTPS传输、设置合理的Token有效期 |
| Token泄露后无法撤销 | 使用黑名单机制（Redis）或设置较短有效期 |
| Payload可被Base64解码 | 不要在Payload中存储敏感信息（Payload只是编码，非加密） |
| 签名算法被攻击（如RS256→HS256） | 严格验证JWT header中的alg字段，使用白名单 |
| 重放攻击 | 使用nonce、jti或时间戳验证 |

**安全签名验证代码**：

```java
// 防御算法切换攻击：严格限制允许的算法
@Component
public class SecureJwtParser {
    
    private final String secret;
    
    public Claims parseToken(String token) {
        return Jwts.parser()
            // 严格指定签名算法，防止算法切换攻击
            .verifyWith(Keys.hmacShaKeyFor(secret.getBytes()))
            // 或使用严格的算法验证器
            .requireAlgorithm(SignatureAlgorithm.HS256)
            .build()
            .parseSignedClaims(token)
            .getPayload();
    }
}
```

## 五、OAuth2资源服务器

### 5.1 OAuth2四种授权模式

在微服务架构中，OAuth2是实现集中式认证的标准方案。Spring Security OAuth2 Resource Server可以轻松验证JWT Token：

```java
// application.yml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: https://your-auth-server.com
          # 或直接指定公钥
          # jwk-set-uri: https://your-auth-server.com/.well-known/jwks.json

// 配置Resource Server
@Configuration
@EnableWebSecurity
public class OAuth2ResourceServerConfig {
    
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) 
            throws Exception {
        http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(Customizer.withDefaults())  // 启用JWT验证
            );
        
        return http.build();
    }
}

// 在Controller中获取JWT中的用户信息
@RestController
@RequestMapping("/api/resource")
public class ResourceController {
    
    @GetMapping("/profile")
    public Map<String, Object> getProfile(
            @AuthenticationPrincipal Jwt jwt) {
        return Map.of(
            "username", jwt.getClaimAsString("sub"),
            "email", jwt.getClaimAsString("email"),
            "roles", jwt.getClaimAsStringList("roles"),
            "iss", jwt.getIssuer().toString()
        );
    }
}
```

### 5.2 令牌校验与失效机制

在生产环境中，需要实现Token的主动失效机制：

```java
// Token黑名单服务
@Service
public class TokenBlacklistService {
    
    @Autowired
    private StringRedisTemplate redisTemplate;
    
    private static final String BLACKLIST_PREFIX = "token:blacklist:";
    
    /**
     * 将Token加入黑名单
     */
    public void blacklistToken(String token, long expirationMillis) {
        String key = BLACKLIST_PREFIX + token.hashCode();
        redisTemplate.opsForValue().set(key, "1", 
            Duration.ofMillis(expirationMillis));
    }
    
    /**
     * 检查Token是否在黑名单中
     */
    public boolean isBlacklisted(String token) {
        String key = BLACKLIST_PREFIX + token.hashCode();
        return Boolean.TRUE.equals(redisTemplate.hasKey(key));
    }
}

// 在JWT过滤器中增加黑名单检查
@Override
protected void doFilterInternal(HttpServletRequest request, 
                                HttpServletResponse response, 
                                FilterChain filterChain) {
    // ...
    if (tokenBlacklistService.isBlacklisted(jwt)) {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.getWriter().write("{\"error\": \"Token已失效\"}");
        return;
    }
    // ...
}

// 登出时将Token加入黑名单
@PostMapping("/logout")
public ResponseEntity<?> logout(@RequestHeader("Authorization") String authHeader) {
    String token = authHeader.substring(7);
    long expiration = jwtUtils.extractClaims(token).getExpiration().getTime() 
        - System.currentTimeMillis();
    tokenBlacklistService.blacklistToken(token, expiration);
    return ResponseEntity.ok("已登出");
}
```

## 六、微服务环境下的认证架构

> **与分布式系统系列的关联**：在微服务架构中，认证服务通常作为独立的Gateway或Auth Service存在。
> 关于分布式系统中的统一认证与OAuth2网关设计，详见《分布式系统面试八股文（五）——分布式服务治理与服务网格》第4节。
> 关于JWT在分布式Session和无状态认证中的应用，详见《分布式系统面试八股文（六）——分布式消息队列与异步架构》附录A。

在微服务架构下，认证的最佳实践通常有两条路线：

**方案一：网关集中认证**（推荐中小型微服务架构）
- 所有请求先经过API Gateway
- Gateway负责JWT Token的验证和用户信息解析
- 通过Header将用户信息传递给下游服务
- 下游服务不再需要验证Token，只信任上游Header

**方案二：服务间Token验证**（适合大型分布式系统）
- 每个服务都作为OAuth2 Resource Server验证Token
- 使用公钥/私钥对，Token由Auth Server签名
- 服务通过Auth Server的公钥端点获取公钥验证签名
- 适合服务数量多、跨团队协作的大型系统

## 七、面试高频问题汇总

### Q1：Spring Security的认证流程是什么？

请参考本文第2.1节的完整流程描述。面试时建议配合组件交互图来描述，从Filter链开始，经过AuthenticationManager、AuthenticationProvider、UserDetailsService，最后到SecurityContextHolder。

### Q2：Spring Security如何实现密码加密和验证？

使用PasswordEncoder接口，BCryptPasswordEncoder是最常用的实现。密码加密使用encode()方法，密码验证使用matches()方法。BCrypt每次加密结果不同是因为有随机盐。

### Q3：hasRole()和hasAuthority()的区别？

hasRole()会自动加上ROLE_前缀，即hasRole("ADMIN")等效于hasAuthority("ROLE_ADMIN")。而hasAuthority()精确匹配，不加前缀。建议用hasRole()检查角色，用hasAuthority()检查具体权限。

### Q4：JWT相比Session有什么优缺点？

JWT的优点：无状态、易于横向扩展、不依赖Cookie、支持跨域、简洁。缺点：无法主动撤销（除非用黑名单）、Payload只是Base64编码不能放敏感信息、Token较长会增加请求体积。

### Q5：如何防止JWT被伪造？

使用HTTPS传输防止中间人攻击；在JWT Header中严格指定算法（防止alg=none攻击）；使用足够长的密钥；验证Token的过期时间、签发者等Claim；考虑使用Token黑名单机制。

### Q6：CSRF攻击是什么？Spring Security如何防护？

CSRF（跨站请求伪造）利用用户已登录的身份，在第三方网站发起恶意请求。防护方式包括：CSRF Token（表单提交时携带Token）、SameSite Cookie（限制Cookie随跨站请求发送）。前后端分离的SPA/REST API通常通过Authorization Header传Token（天然不受Cookie限制），因此可以禁用CSRF防护。

### Q7：Spring Security的@PreAuthorize如何使用SpEL表达式？

@PreAuthorize注解使用SpEL（Spring Expression Language）编写权限表达式。常用表达式包括：hasRole()、hasAuthority()、hasAnyRole()、permitAll()、denyAll()、#username==authentication.name（引用参数）、@beanName.method()（调用Bean方法）等。

### Q8：OAuth2的四种授权模式分别适用什么场景？

| 模式 | 适用场景 |
|------|----------|
| 授权码模式（Authorization Code） | 有后端的Web应用，安全性最高 |
| 简化模式（Implicit） |纯前端SPA应用（已被OAuth2.1废弃） |
| 密码模式（Password Credentials） | 高度信任的自家应用 |
| 客户端凭证（Client Credentials） | 服务间调用（Machine to Machine） |

---

## 📌 下期预告

**Spring面试八股文（八）——Spring Boot进阶：外部化配置与Profile实战**

在第八篇中，我们将深入探讨Spring Boot的外部化配置机制和Profile多环境管理。包括：

- Spring Boot自动配置的底层原理与@ConfigurationProperties
- @Value、@ConfigurationProperties、@Environment的对比与最佳实践
- Profile的激活方式与多环境配置优先级
- 配置文件的加密与敏感信息管理
- Spring Boot 3.x新特性：Java 17+、AOT编译、GraalVM原生镜像

掌握配置管理是构建可部署Spring应用的基础，也是面试中的高频考点。

---

> **推荐阅读**：
> - 《[Spring面试八股文（一）——Spring核心概念与IoC容器]》
> - 《[Spring面试八股文（二）——Spring AOP与事务管理]》
> - 《[Spring面试八股文（三）——Spring MVC核心原理与Spring Boot自动配置]》
> - 《[Spring Cloud微服务架构实战]》（深度解析）
> - 《[分布式系统面试八股文（三）——分布式事务与一致性解决方案]》
> - 《[微服务面试八股文（三）——微服务配置中心、API网关与安全认证]》
