所有工作时产生的临时脚本/文件放入temp/文件夹，用完删除。
每次新增/调整表结构后，注意更新init.sql，将之前库清空。
当需要更新导入数据时，注意个更新load.py而不是import.sql，import.sql由load.py生成。每次生成import.sql时记得情况原来的数据。
新增端点后，注意更新doc/api_usage.md