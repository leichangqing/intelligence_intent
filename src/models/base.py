"""
基础数据模型
"""
from datetime import datetime
from peewee import *
from src.config.database import BaseModel


class TimestampMixin(Model):
    """时间戳混入类"""
    created_at = DateTimeField(default=datetime.now, verbose_name="创建时间")
    updated_at = DateTimeField(default=datetime.now, verbose_name="更新时间")
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """重写保存方法，自动更新时间戳"""
        # 如果是更新操作，更新updated_at字段
        if self.id:
            self.updated_at = datetime.now()
        return super().save(*args, **kwargs)


class SoftDeleteMixin(Model):
    """软删除混入类"""
    is_deleted = BooleanField(default=False, verbose_name="是否删除")
    deleted_at = DateTimeField(null=True, verbose_name="删除时间")
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """软删除方法"""
        self.is_deleted = True
        self.deleted_at = datetime.now()
        self.save()
    
    def restore(self):
        """恢复删除方法"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class AuditMixin(Model):
    """审计混入类"""
    created_by = CharField(max_length=100, null=True, verbose_name="创建者")
    updated_by = CharField(max_length=100, null=True, verbose_name="更新者")
    
    class Meta:
        abstract = True
    
    def set_creator(self, user_id: str):
        """设置创建者"""
        if not self.id:  # 仅在新建时设置
            self.created_by = user_id
    
    def set_updater(self, user_id: str):
        """设置更新者"""
        self.updated_by = user_id


class CommonModel(BaseModel, TimestampMixin):
    """通用模型基类"""
    
    class Meta:
        abstract = True


class AuditableModel(CommonModel, AuditMixin):
    """可审计的模型基类"""
    
    class Meta:
        abstract = True


class SoftDeleteModel(CommonModel, SoftDeleteMixin):
    """支持软删除的模型基类"""
    
    class Meta:
        abstract = True
    
    @classmethod
    def select_active(cls):
        """查询未删除的记录"""
        return cls.select().where(cls.is_deleted == False)
    
    @classmethod
    def select_deleted(cls):
        """查询已删除的记录"""
        return cls.select().where(cls.is_deleted == True)