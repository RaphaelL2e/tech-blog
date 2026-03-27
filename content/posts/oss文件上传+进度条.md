---
title: "OSS文件上传+进度条"
date: 2019-10-23T20:13:09+08:00
draft: false
categories: ['JAVA']
tags: ['java', 'oss']
---

# [](#文件上传——ossutil-putObject)文件上传——ossutil.putObject

## [](#工具类)工具类

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90
91
92
93
94
95
96
97
98
99
100
101
102
103
104
105
106
107
108
109
110
111
112
113
114
115
116
117
118
119
120
121
122
123
124
125
126
127
128
129
130
131
132
133
134
135
136
137
138
139
140
141
142
143
144
145
146
147
148
149
150
151
152
153
154
155
156
157
158
159
160
161
162
163
164
165
166
167
168
169
170
171
172
173
174
175
176
177
178
179
180
181
182
183
184
185
186
187
188
189
190
191
192
193
194
195
196
197
198
199
200
201
202
203
204
205
206
207
//工具类
package com.*.website.util;

import com.aliyun.oss.ClientException;
import com.aliyun.oss.OSSClient;
import com.aliyun.oss.OSSException;
import com.aliyun.oss.event.ProgressEvent;
import com.aliyun.oss.event.ProgressEventType;
import com.aliyun.oss.event.ProgressListener;
import com.aliyun.oss.model.CannedAccessControlList;
import com.aliyun.oss.model.CreateBucketRequest;
import com.aliyun.oss.model.PutObjectRequest;
import com.aliyun.oss.model.PutObjectResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;
import java.io.File;
import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.UUID;

import static com.*.website.config.OSSConstantProperties.*;

/**
 * @author:leeyf
 * @create: 2019-07-26 09:42
 * @Description: OSS工具类
 */
public class OSSUtil {
    /**
     * The uploading progress listener. Its progressChanged API is called by the SDK when there's an update.
     */
    static class PutObjectProgressListener implements ProgressListener {
        private HttpSession session;
        private long bytesWritten = 0;
        private long totalBytes = -1;
        private boolean succeed = false;
        private int percent = 0;

        //构造方法中加入session
        public PutObjectProgressListener() {
        }
        public PutObjectProgressListener(HttpSession mSession) {
            this.session = mSession;
            session.setAttribute("upload_percent", percent);
        }

        @Override
        public void progressChanged(ProgressEvent progressEvent) {
            long bytes = progressEvent.getBytes();
            ProgressEventType eventType = progressEvent.getEventType();
            switch (eventType) {
                case TRANSFER_STARTED_EVENT:
                    System.out.println("Start to upload......");
                    break;

                case REQUEST_CONTENT_LENGTH_EVENT:
                    this.totalBytes = bytes;
                    System.out.println(this.totalBytes + " bytes in total will be uploaded to OSS");
                    break;

                case REQUEST_BYTE_TRANSFER_EVENT:
                    this.bytesWritten += bytes;
                    if (this.totalBytes != -1) {
                        int percent = (int)(this.bytesWritten * 100.0 / this.totalBytes);
                        //将进度percent放入session中
                        session.setAttribute("upload_percent", percent);

                        logger.info(bytes + " bytes have been written at this time, upload progress: " +
                                percent + "%(" + this.bytesWritten + "/" + this.totalBytes + ")");
                    } else {
                        logger.info(bytes + " bytes have been written at this time, upload ratio: unknown" +
                                "(" + this.bytesWritten + "/...)");
                    }
                    break;

                case TRANSFER_COMPLETED_EVENT:
                    this.succeed = true;
                    System.out.println("Succeed to upload, " + this.bytesWritten + " bytes have been transferred in total");
                    break;

                case TRANSFER_FAILED_EVENT:
                    System.out.println("Failed to upload, " + this.bytesWritten + " bytes have been transferred");
                    break;

                default:
                    break;
            }
        }

        public boolean isSucceed() {
            return succeed;
        }
    }
    static Logger logger = LoggerFactory.getLogger(OSSUtil.class);
    //oss访问域名，在oss后台添加bucket之后 查看
    private static String endpoint = JAVA4ALL_END_POINT;
    // accessKeyId和accessKeySecret是OSS的访问密钥
    private static String accessKeyId = JAVA4ALL_ACCESS_KEY_ID;
    private static String accessKeySecret = JAVA4ALL_ACCESS_KEY_SECRET;
    //bucketName
    private static String bucketName = JAVA4ALL_BUCKET_NAME;
    // Object是OSS存储数据的基本单元，称为OSS的对象，也被称为OSS的文件
    private static String fileHost = JAVA4ALL_FILE_HOST;

    static SimpleDateFormat format = new SimpleDateFormat("yyyyMMdd");
    static String dateStr = format.format(new Date());

    //文件上传
    public static String upload(File file, HttpServletRequest request) throws UnsupportedEncodingException {

        if(null == file){
            return null;
        }
        OSSClient ossClient = new OSSClient(endpoint,accessKeyId,accessKeySecret);
        //容器不存在，就创建
        if(! ossClient.doesBucketExist(bucketName)){
            ossClient.createBucket(bucketName);
            CreateBucketRequest createBucketRequest = new CreateBucketRequest(bucketName);
            createBucketRequest.setCannedACL(CannedAccessControlList.PublicRead);
            ossClient.createBucket(createBucketRequest);
        }
        //创建文件路径
        String fileUrl = fileHost+"/"+(dateStr + "/" + UUID.randomUUID().toString().replace("-","")+"-"+file.getName());
        try {
            //ossClient.putObject(new PutObjectRequest(bucketName, fileUrl, file)).<PutObjectRequest>withProgressListener(new PutObjectProgressListener()));
            //设置权限 这里是公开读
            ossClient.setBucketAcl(bucketName,CannedAccessControlList.PublicRead);
            //上传文件
            PutObjectResult result = ossClient.putObject(new PutObjectRequest(bucketName, fileUrl, file)
                    .<PutObjectRequest>withProgressListener(new PutObjectProgressListener(request.getSession())));
            if(null != result){
                logger.info("==========>OSS文件上传成功,OSS地址："+fileUrl);
                logger.info("==========>OSS文件上传成功,访问地址："+URL+fileUrl);
                return URL+fileUrl;
            }
        } catch (OSSException oe) {
            logger.error("Caught an OSSException, which means your request made it to OSS, "
                    + "but was rejected with an error response for some reason.Error Message: " + oe.getErrorCode()
                    + "Error Code:" + oe.getErrorCode() + "Request ID:" + oe.getRequestId() + "Host ID:" + oe.getHostId(), oe);
            throw new OSSException(oe.getErrorMessage(), oe);
        } catch (ClientException ce) {
            logger.error("Caught an ClientException, which means the client encountered "
                    + "a serious internal problem while trying to communicate with OSS, "
                    + "such as not being able to access the network.Error Message:" + ce.getMessage(), ce);
            throw new ClientException(ce);
        } finally {
            //关闭
            ossClient.shutdown();
        }

        return null;
    }

    //文件上传
    public static String uploadMultipartFile(MultipartFile multipartFile) throws IOException {
        // 获取文件名
        String fileName = multipartFile.getOriginalFilename();
        // 获取文件后缀
        String prefix=fileName.substring(fileName.lastIndexOf("."));
        // 用uuid作为文件名，防止生成的临时文件重复
        final File excelFile = File.createTempFile(UUID.randomUUID().toString(), prefix);

        multipartFile.transferTo(excelFile);
        if(null == excelFile){
            return null;
        }
        OSSClient ossClient = new OSSClient(endpoint,accessKeyId,accessKeySecret);
        //容器不存在，就创建
        if(! ossClient.doesBucketExist(bucketName)){
            ossClient.createBucket(bucketName);
            CreateBucketRequest createBucketRequest = new CreateBucketRequest(bucketName);
            createBucketRequest.setCannedACL(CannedAccessControlList.PublicRead);
            ossClient.createBucket(createBucketRequest);
        }
        //创建文件路径
        String fileUrl = fileHost+"/"+(dateStr + "/" + UUID.randomUUID().toString().replace("-","")+"-"+multipartFile.getName());
        //上传文件
        PutObjectResult result = ossClient.putObject(new PutObjectRequest(bucketName, fileUrl, excelFile));
        //设置权限 这里是公开读
        ossClient.setBucketAcl(bucketName,CannedAccessControlList.PublicRead);

        if(null != result){
            logger.info("==========>OSS文件上传成功,OSS地址："+fileUrl);
            logger.info("==========>OSS文件上传成功,访问地址："+URL+fileUrl);
            return URL+fileUrl;
        }
        //关闭
        ossClient.shutdown();
        return null;
    }

    public static void delete(String url){
        String[] strings= url.split(".com/");
        OSSClient ossClient = new OSSClient(endpoint,accessKeyId,accessKeySecret);
        ossClient.deleteObject(bucketName,strings[1]);
        logger.info("==========>OSS文件删除成功");

    }

}

## [](#控制层)控制层

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90
91
92
93
94
95
96
97
98
99
100
101
102
//控制层
package com.*.website.controller;

import com.*.website.enums.ErrorCodeEnum;
import com.*.website.response.ServerResponse;
import com.*.website.util.OSSUtil;
import io.swagger.annotations.ApiOperation;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;
import java.io.File;
import java.io.IOException;
import java.util.UUID;

@RestController
@RequestMapping("/oss")
public class OSSController {

    /**
     * 上传文件
     * @param file 文件
     * @return ServerResponse
     */
    @ApiOperation("通用上传文件接口")
    @PostMapping("/uploadFile")
    public ServerResponse<Object> uploadFile(MultipartFile file,HttpServletRequest request){

        try {

            // 获取文件名
            String fileName = file.getOriginalFilename();
            // 获取文件后缀
            assert fileName != null;
            String prefix=fileName.substring(fileName.lastIndexOf("."));
            // 用uuid作为文件名，防止生成的临时文件重复
            final File excelFile = File.createTempFile(UUID.randomUUID().toString(), prefix);

            file.transferTo(excelFile);

            String url = OSSUtil.upload(excelFile,request);

            //程序结束时，删除临时文件
            deleteFile(excelFile);

            return ServerResponse.createBySuccess(url);

        } catch (Exception e){
            e.printStackTrace();
            return ServerResponse.createByErrorCodeMessage(ErrorCodeEnum.IMAGE_UPLOAD_ERROR);
        }

    }
    @ApiOperation("通用图片上传接口")
    @PostMapping("/uploadPic")
    public ServerResponse uploadPic(MultipartFile file) throws IOException {
        String url= OSSUtil.uploadMultipartFile(file);
        return ServerResponse.createBySuccess(url);
    }

    /**
     * 删除
     * @param files 文件们
     */
    private void deleteFile(File... files) {
        for (File file : files) {
            if (file.exists()) {
                file.deleteOnExit();
            }
        }
    }

    /**
     * 获取实时长传进度
     * @param request
     * @return
     */
    @GetMapping("/item/percent")
    @ResponseBody
    public int getUploadPercent(HttpServletRequest request){
        HttpSession session = request.getSession();
        int percent = session.getAttribute("upload_percent") == null ? 0: (int) session.getAttribute("upload_percent");
        return percent;
    }

    /**
     * 重置上传进度
     * @param request
     * @return
     */
    @GetMapping ("/percent/reset")
    public void resetPercent(HttpServletRequest request){
        HttpSession session = request.getSession();
        session.setAttribute("upload_percent",0);
    }

}

## [](#配置类)配置类

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
//配置类
package com.*.website.config;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OSSConstantProperties implements InitializingBean {

    @Value("${java4all.file.endpoint}")
    private String java4all_file_endpoint;

    @Value("${java4all.file.keyid}")
    private String java4all_file_keyid;

    @Value("${java4all.file.keysecret}")
    private String java4all_file_keysecret;

    @Value("${java4all.file.filehost}")
    private String java4all_file_filehost;

    @Value("${java4all.file.bucketname}")
    private String java4all_file_bucketname;

    public static String JAVA4ALL_END_POINT         ;
    public static String JAVA4ALL_ACCESS_KEY_ID     ;
    public static String JAVA4ALL_ACCESS_KEY_SECRET ;
    public static String JAVA4ALL_BUCKET_NAME       ;
    public static String JAVA4ALL_FILE_HOST         ;
    public static String URL ="https://*.oss-cn-beijing.aliyuncs.com/"         ;
    @Override
    public void afterPropertiesSet() throws Exception {
        JAVA4ALL_END_POINT = java4all_file_endpoint;
        JAVA4ALL_ACCESS_KEY_ID = java4all_file_keyid;
        JAVA4ALL_ACCESS_KEY_SECRET = java4all_file_keysecret;
        JAVA4ALL_FILE_HOST = java4all_file_filehost;
        JAVA4ALL_BUCKET_NAME = java4all_file_bucketname;
    }
}

基础的文件上传跟进度条添加都有，具体的可以看备注

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝