# FINYUE · OPC盖章 1.0.0

FINYUE 自有的免费 Windows 本机 PDF 工作台，由凛野（北京）文化传媒有限公司维护和发布。提供自有图形章、本人签名图片、日期、文字、申请审核和副本导出。**图片盖章不提供可靠电子签名认证、可信时间戳或印章备案。**

[官网介绍](https://finyue.com/products/opc-seal) · [首版下载与对应源码](https://github.com/Liwinter94264/FINYUE-OPC-SEAL/releases/tag/v1.0.0) · [问题反馈](https://github.com/Liwinter94264/FINYUE-OPC-SEAL/issues)

## 下载和使用

下载 FINYUE-OPC-Seal-1.0.0-Windows-x64.zip，解压到有写入权限的文件夹后双击 EXE。支持 Windows 10/11 x64，无需安装 Python。下载包包括许可和使用说明；SHA256SUMS.txt 用于核对发行文件。首版没有发行者代码签名，不要把文件校验值当作身份认证证书，只从官方页面下载。

1. 首次注册填写显示姓名、5位数字编号和至少8位密码，阅读勾选服务协议与免责声明。首个成功注册者成为这份本机数据的管理员，其后为申请人；没有预置真实用户或印章。每次打开和退出登录后均须密码，旧会话与本机自动登录配置不恢复登录。
2. 在印章 / 导出设置中填写有权使用的名称，或导入自有印章图片；设置默认导出文件夹。核查真实用印授权，本机管理员角色和显示姓名不证明真实身份或审批权限。
3. 选择 PDF，可自动定位当前页右下角或点击放置。签名支持姓名字样、本人手写图片去白底；日期和文字可添加、编辑、删除与移动。预览支持缩放、滚动和最近50步撤销。
4. 核对每页内容、素材、日期与位置。管理员本人提交自动通过，没有第二人复核；申请人由管理员审核。通过后导出副本，成功提示显示保存路径，原件和已有文件不覆盖。
5. 待审管理员可调整位置，申请人不可；已通过、退回、撤回和作废均只读。管理员可作废已通过记录，随后工具禁止再次导出。**作废不能撤销已发送的副本**，经办人须联系接收方停用并补正。

PDF 最大50MB、500页，不支持加密或已填有效数字签名的 PDF。图片最大10MB、1600万像素。Word 先导出 PDF。账号与官网独立；审核在同一电脑完成，没有远程多机审批。

## 文件与隐私

本版本没有云同步、文件上传、后台遥测或自动更新。账号、素材、副本和操作记录在 EXE 旁的 data/；导出在用户选择的位置。密码保存为加盐派生值，但文件和数据库没有整体加密，记录也不是不可篡改存证。能写入程序或数据的人可能绕过应用控制。使用者负责系统权限、备份和保存期限。

不要在公开 Issues 发布真实文件、印章、个人签名、账号库、密码或本机配置；只提交脱敏描述和合成例子。软件内使用规则提供协议、免责声明、完整 AGPL 和全部第三方许可，离线可看；同意记录保存版本、正文SHA256与时间，规则变化需重新确认。

## 开源许可

应用代码与匿名装饰采用 **GNU AGPL v3（AGPL-3.0-only）**。完整文本见 [LICENSE](LICENSE)，产品身份见 [COPYRIGHT.md](COPYRIGHT.md)。第三方版权和许可保留，见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 和 licenses/。

分发程序或修改版时按许可提供完整对应源码及通知。修改本程序后让用户通过网络与之交互时，向这些用户提供修改版对应源码。普通本机使用者不必公开自己的 PDF、印章或签名。代码许可不自动授予 FINYUE 商标权；修改版不得误称为 FINYUE 官方发行版。软件内使用协议不额外限制开源许可授予的权利。

官方同一 Release 提供应用源码ZIP、未修改上游依赖源码ZIP及SHA256，无需付费或申请权限。UPSTREAM-SOURCES.json 记录源文件、版本、来源和哈希；上游源码ZIP单独包含 MuPDF 1.28.2 及其原生第三方源码、Pillow Windows 原生图像依赖和 libavif 编码器输入。Pillow 上游构建脚本中的补丁保留在其原始源码中，发行方没有另行修改第三方源码。

## 从源码构建

Windows x64、Python 3.12.14、系统 Tk 8.6 和 Windows 自带宋体/楷体，系统字体不分发。核心依赖锁定在 requirements.txt；源码独立于私人开发历史。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m unittest -v test_seal_core test_signature_session test_export_undo test_profile test_registration test_auth_ui
.venv/Scripts/python -m PyInstaller --clean --noconfirm OPC盖章.spec
```

结果：dist/FINYUE-OPC-Seal-1.0.0-Windows-x64.exe。spec 按相对路径加载匿名资产与许可，不含私人配置或正式吉祥物。--smoke-test smoke-result.json 可检查合成文件导出与撤销，不读取现有 data/。不同环境可能导致EXE字节不同，不承诺逐字节可复现。

PyMuPDF 源码包内 setup.py、pyproject.toml 和 MuPDF 脚本是未修改的原生构建入口。从原生源码构建须按上游说明准备 Windows C/C++ 工具链；源版本在 UPSTREAM-SOURCES.json 固定。应用分发白名单生成器为 prepare_source.py。

## 升级

关闭旧程序，把新版放到旧 EXE 同目录，保留旧 EXE 和完整 data/，不要用发行包覆盖数据。不要删除原账号库重建管理员。旧私人默认配置不进入公开包；1.0.0 强制密码登录。新协议在首次进入工作台时重新确认，原账号和审核记录保留。升级后新增素材记录继续由新版处理，旧版可能不能理解新字段。
