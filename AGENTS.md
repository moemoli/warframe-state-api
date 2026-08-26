## 临时文件处理
所有工作时产生的临时脚本/文件放入temp/文件夹，用完删除。包括临时产生的sql，如果是调整表结构产生的sql，记得并入init.sql

## API 端点新增/修改
新增/修改端点后需要再doc/api/下新增/修改对应端点的说明，并同时更新其索引doc/api/README.md

## 数据库处理
初始化数据库建表时将init.sql导入。
每次新增/调整表结构后，注意更新init.sql，将之前表清空重新导入。

## 导入数据处理
当需要更新导入数据时，注意更新load.py而不是import.sql。import.sql由load.py生成。每次生成import.sql时记得清空原来的数据。生成后导入import.sql即可。

### 项目说明

## 根目录
项目根目录解析以下数据并提供API服务：
- Warframe官方Public Export Plus
- Warframe 官方 World State
- Warframe Market 市场解析

## 插件目录(plugin/*)
目前有Astrbot插件，开发文档为: https://docs.astrbot.app/dev/star/plugin-new.html.
开发时先将Astrbot本体(https://github.com/AstrBotDevs/AstrBot)clone到temp/Astrbot下，然后将plugin/astrbot软连接到temp/Astrbot/data/plugins/astrbot_plugin_warframe_helper.
Astrbot作为测试与引用使用，不得修改其代码。