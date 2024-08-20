# amzju
可模拟用户统一认证登录应用服务的流程，用于第三方代替用户调用部分API。

**本项目仅供学习、研究技术使用。以任何方式使用本项目代码或构建产物需自负后果。**

## 运行
需要Python 3.10+，建议使用Python 3.12。  
1. (可选) 创建虚拟环境：`python -m venv ./.venv`并启用该环境(on Windows: `.\.venv\Scripts\activate`)
2. 安装依赖：`pip install -r requirements.txt`
3. 创建`local.config.json`并参照`config.json`自行修改需要的配置(相同配置项，前者覆盖后者)。
4. 使用`python main.py`启动服务。如需热重载(开发时)，可使用`fastapi dev`。

## BypassCORS模式
由于CORS和Cookie等的限制，第三方服务的前端不能直接向统一认证发请求，更无法获取登录后的cookie等凭据。  
此时可使用amzju作为后端的一部分，调用amzju登录和代理请求(需要用户提供明文用户名+密码)。

#### 使用方式
调用`/proxy/text`API。需提供用户名密码/token、请求的method/url/headers/body。此API响应的状态码、headers、正文都和上游返回一致。  
若于服务器上使用，请注意修改`cors_allow_origins`和`username_filter`配置项。
 
## Approve模式
面向安全需求更高的用户。  
您可能不希望向第三方暴露您的密码原文。您可以自行搭建amzju服务端(可视情况直接使用环回地址)，让支持此模式的第三方前端直接向您控制的amzju服务端发送请求，密码仅保存在您控制的服务器上。您可以自行设置passphrase，也可以过滤请求(需自行修改代码)。  

#### 使用方式
在local.credential.json设置您的密码。格式如下：
```json
[{
    "username": "3230000000",
    "password": "your_password",
    "passphrase": "(optional)your_passphrase",
    "require_confirm": false
}]
```
`passphrase`可省略。若省略，启动时会随机生成passphrase并打印。  
`require_confirm`可省略(默认为`false`)。若为`true`，则使用正确的passphrase调用后，仍然需要手动确认(控制台确认\[Y/n])。

设置完毕后，启动服务。在支持此模式的第三方应用提供您的Endpoint(默认情况下为`http://localhost:8899`)和passphrase，其即可调用API。