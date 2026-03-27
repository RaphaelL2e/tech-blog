---
title: "Elasticsearch回顾"
date: 2019-10-17T21:19:34+08:00
draft: false
categories: ['JAVA']
tags: ['java', 'elasticsearch']
---

之前做一个社区得时候，使用过的技术——elasticsearch，最近因为需要做一个全站文章搜索，再次使用到它。由于之前使用，并没有留存笔记，这次使用过程中需要反复查一些资料，所以做一些必要的保留，方便下次使用回顾。

### [](#部署)部署

[官网地址](https://www.elastic.co/cn/downloads/) 

elasticsearch官网有详细的安装部署文档，不再赘述。

### [](#分词器)分词器

常见的es分词器：[ik](https://github.com/medcl/elasticsearch-analysis-ik)

### [](#内容)内容

#### [](#概念)概念

Cluster　集群　一个或多个节点的集合，由唯一名称标识。

Node 节点 一台服务器，集群的一部分，存储数据并参与集群的索引和搜索功能

Index 索引 对应了 数据库

type 类型 对应数据表

[主要使用的全文查询](https://www.elastic.co/guide/en/elasticsearch/reference/6.0/full-text-queries.html)

#### [](#代码)代码

1
2
3
4
5
 BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();  //与文档匹配的查询，该文档与其他查询的布尔组合匹配。 [1]
boolQuery
                .must(QueryBuilders.matchQuery("status",articleSearchForm.getStatus()))// 必须匹配的查询
                .must(QueryBuilders.matchQuery("label",articleSearchForm.getType()))
                .must(QueryBuilders.queryStringQuery(articleSearchForm.getSearchWord()).analyzeWildcard(true).defaultField("*")) //宽泛的查询

- [文档](http://xbib.org/elasticsearch/2.1.1/apidocs/org/elasticsearch/index/query/BoolQueryBuilder.html)

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝