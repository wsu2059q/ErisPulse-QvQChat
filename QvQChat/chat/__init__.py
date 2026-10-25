"""聊天域子包（拆分自 Main.py）：入口聚合 / 用量记账 / 聊天命令。

拆分方式为 mixin：Main 继承 InboxMixin/UsageMixin/CliMixin，
类上的公开与私有方法名保持不变（tests 通过 getattr_static(Main, name) 绑定）。
"""
