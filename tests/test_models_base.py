"""
基础模型单元测试
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json

from src.models.base import BaseModel


class TestBaseModel:
    """基础模型测试类"""
    
    def test_base_model_creation(self):
        """测试基础模型创建"""
        # 创建模型实例
        model = BaseModel()
        
        # 验证基础字段
        assert hasattr(model, 'id')
        assert hasattr(model, 'created_at')
        assert hasattr(model, 'updated_at')
        assert hasattr(model, 'is_active')
        
        # 验证默认值
        assert model.is_active == True
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)
    
    def test_base_model_to_dict(self):
        """测试模型转字典"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        model.created_at = datetime(2024, 1, 1, 10, 0, 0)
        model.updated_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 转换为字典
        model_dict = model.to_dict()
        
        # 验证字典内容
        assert isinstance(model_dict, dict)
        assert model_dict['id'] == 1
        assert model_dict['is_active'] == True
        assert 'created_at' in model_dict
        assert 'updated_at' in model_dict
    
    def test_base_model_from_dict(self):
        """测试从字典创建模型"""
        # 准备测试数据
        model_data = {
            'id': 1,
            'is_active': True,
            'created_at': '2024-01-01T10:00:00',
            'updated_at': '2024-01-01T10:00:00'
        }
        
        # 从字典创建模型
        model = BaseModel.from_dict(model_data)
        
        # 验证模型属性
        assert model.id == 1
        assert model.is_active == True
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)
    
    def test_base_model_update(self):
        """测试模型更新"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        original_updated_at = model.updated_at
        
        # 更新模型
        update_data = {
            'is_active': False
        }
        
        model.update(update_data)
        
        # 验证更新
        assert model.is_active == False
        assert model.updated_at > original_updated_at
    
    def test_base_model_soft_delete(self):
        """测试软删除"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        model.is_active = True
        
        # 软删除
        model.soft_delete()
        
        # 验证软删除
        assert model.is_active == False
        assert hasattr(model, 'deleted_at')
        assert model.deleted_at is not None
    
    def test_base_model_restore(self):
        """测试恢复软删除"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        model.is_active = False
        model.deleted_at = datetime.now()
        
        # 恢复
        model.restore()
        
        # 验证恢复
        assert model.is_active == True
        assert model.deleted_at is None
    
    def test_base_model_validation(self):
        """测试模型验证"""
        # 创建模型实例
        model = BaseModel()
        
        # 验证方法应该返回True（基础模型没有特殊验证）
        assert model.validate() == True
    
    def test_base_model_save(self):
        """测试保存模型"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 模拟保存操作
        with patch.object(model, 'save') as mock_save:
            mock_save.return_value = model
            
            # 保存模型
            result = model.save()
            
            # 验证保存
            assert result == model
            mock_save.assert_called_once()
    
    def test_base_model_delete(self):
        """测试删除模型"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 模拟删除操作
        with patch.object(model, 'delete_instance') as mock_delete:
            mock_delete.return_value = 1
            
            # 删除模型
            result = model.delete_instance()
            
            # 验证删除
            assert result == 1
            mock_delete.assert_called_once()
    
    def test_base_model_bulk_create(self):
        """测试批量创建"""
        # 准备测试数据
        models_data = [
            {'id': 1, 'is_active': True},
            {'id': 2, 'is_active': True},
            {'id': 3, 'is_active': False}
        ]
        
        # 模拟批量创建
        with patch.object(BaseModel, 'insert_many') as mock_insert:
            mock_insert.return_value = MagicMock(execute=MagicMock(return_value=3))
            
            # 批量创建
            result = BaseModel.bulk_create(models_data)
            
            # 验证批量创建
            assert result == 3
            mock_insert.assert_called_once()
    
    def test_base_model_bulk_update(self):
        """测试批量更新"""
        # 准备测试数据
        update_data = {'is_active': False}
        condition = BaseModel.id.in_([1, 2, 3])
        
        # 模拟批量更新
        with patch.object(BaseModel, 'update') as mock_update:
            mock_query = MagicMock()
            mock_query.where.return_value.execute.return_value = 3
            mock_update.return_value = mock_query
            
            # 批量更新
            result = BaseModel.bulk_update(update_data, condition)
            
            # 验证批量更新
            assert result == 3
    
    def test_base_model_get_by_id(self):
        """测试根据ID获取模型"""
        # 准备测试数据
        model_id = 1
        
        # 模拟获取操作
        with patch.object(BaseModel, 'get_by_id') as mock_get:
            mock_model = BaseModel()
            mock_model.id = model_id
            mock_get.return_value = mock_model
            
            # 获取模型
            result = BaseModel.get_by_id(model_id)
            
            # 验证获取
            assert result.id == model_id
            mock_get.assert_called_once_with(model_id)
    
    def test_base_model_get_or_none(self):
        """测试获取模型或返回None"""
        # 准备测试数据
        model_id = 999
        
        # 模拟获取操作（不存在）
        with patch.object(BaseModel, 'get_or_none') as mock_get:
            mock_get.return_value = None
            
            # 获取模型
            result = BaseModel.get_or_none(BaseModel.id == model_id)
            
            # 验证获取
            assert result is None
            mock_get.assert_called_once()
    
    def test_base_model_exists(self):
        """测试检查模型是否存在"""
        # 准备测试数据
        model_id = 1
        
        # 模拟存在检查
        with patch.object(BaseModel, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value.exists.return_value = True
            mock_select.return_value = mock_query
            
            # 检查存在
            result = BaseModel.exists(BaseModel.id == model_id)
            
            # 验证存在
            assert result == True
    
    def test_base_model_count(self):
        """测试计数"""
        # 模拟计数操作
        with patch.object(BaseModel, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.count.return_value = 5
            mock_select.return_value = mock_query
            
            # 计数
            result = BaseModel.count()
            
            # 验证计数
            assert result == 5
    
    def test_base_model_pagination(self):
        """测试分页"""
        # 准备测试数据
        page = 2
        page_size = 10
        
        # 模拟分页操作
        with patch.object(BaseModel, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.paginate.return_value = [BaseModel() for _ in range(page_size)]
            mock_select.return_value = mock_query
            
            # 分页查询
            result = BaseModel.paginate(page, page_size)
            
            # 验证分页
            assert len(result) == page_size
    
    def test_base_model_ordering(self):
        """测试排序"""
        # 模拟排序操作
        with patch.object(BaseModel, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.order_by.return_value = [BaseModel() for _ in range(3)]
            mock_select.return_value = mock_query
            
            # 排序查询
            result = BaseModel.order_by(BaseModel.created_at.desc())
            
            # 验证排序
            assert len(result) == 3
    
    def test_base_model_filtering(self):
        """测试过滤"""
        # 模拟过滤操作
        with patch.object(BaseModel, 'select') as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = [BaseModel() for _ in range(2)]
            mock_select.return_value = mock_query
            
            # 过滤查询
            result = BaseModel.filter(BaseModel.is_active == True)
            
            # 验证过滤
            assert len(result) == 2
    
    def test_base_model_json_serialization(self):
        """测试JSON序列化"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        model.is_active = True
        model.created_at = datetime(2024, 1, 1, 10, 0, 0)
        
        # 序列化为JSON
        json_str = model.to_json()
        
        # 验证JSON
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data['id'] == 1
        assert data['is_active'] == True
    
    def test_base_model_json_deserialization(self):
        """测试JSON反序列化"""
        # 准备JSON数据
        json_data = {
            'id': 1,
            'is_active': True,
            'created_at': '2024-01-01T10:00:00',
            'updated_at': '2024-01-01T10:00:00'
        }
        json_str = json.dumps(json_data)
        
        # 从JSON创建模型
        model = BaseModel.from_json(json_str)
        
        # 验证模型
        assert model.id == 1
        assert model.is_active == True
        assert isinstance(model.created_at, datetime)
    
    def test_base_model_repr(self):
        """测试模型字符串表示"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 获取字符串表示
        repr_str = repr(model)
        
        # 验证字符串表示
        assert 'BaseModel' in repr_str
        assert 'id=1' in repr_str
    
    def test_base_model_str(self):
        """测试模型字符串"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 获取字符串
        str_repr = str(model)
        
        # 验证字符串
        assert isinstance(str_repr, str)
        assert len(str_repr) > 0
    
    def test_base_model_eq(self):
        """测试模型相等性"""
        # 创建两个相同的模型实例
        model1 = BaseModel()
        model1.id = 1
        
        model2 = BaseModel()
        model2.id = 1
        
        # 创建不同的模型实例
        model3 = BaseModel()
        model3.id = 2
        
        # 验证相等性
        assert model1 == model2
        assert model1 != model3
    
    def test_base_model_hash(self):
        """测试模型哈希"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 获取哈希值
        hash_value = hash(model)
        
        # 验证哈希值
        assert isinstance(hash_value, int)
        assert hash_value == hash(model)  # 哈希值应该一致
    
    def test_base_model_copy(self):
        """测试模型复制"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        model.is_active = True
        
        # 复制模型
        copied_model = model.copy()
        
        # 验证复制
        assert copied_model.id == model.id
        assert copied_model.is_active == model.is_active
        assert copied_model is not model  # 应该是不同的对象
    
    def test_base_model_clean(self):
        """测试模型清理"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 清理模型
        model.clean()
        
        # 验证清理（基础模型的clean方法应该不做任何操作）
        assert model.id == 1
    
    def test_base_model_full_clean(self):
        """测试完整清理"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 完整清理
        model.full_clean()
        
        # 验证完整清理
        assert model.id == 1
    
    def test_base_model_refresh(self):
        """测试刷新模型"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        
        # 模拟刷新操作
        with patch.object(model, 'refresh') as mock_refresh:
            mock_refresh.return_value = model
            
            # 刷新模型
            result = model.refresh()
            
            # 验证刷新
            assert result == model
            mock_refresh.assert_called_once()
    
    def test_base_model_get_dirty_fields(self):
        """测试获取脏字段"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        model.is_active = True
        
        # 修改字段
        model.is_active = False
        
        # 获取脏字段
        dirty_fields = model.get_dirty_fields()
        
        # 验证脏字段
        assert 'is_active' in dirty_fields
        assert dirty_fields['is_active'] == False
    
    def test_base_model_is_dirty(self):
        """测试检查是否有脏数据"""
        # 创建模型实例
        model = BaseModel()
        model.id = 1
        model.is_active = True
        
        # 检查脏数据（应该为False）
        assert model.is_dirty() == False
        
        # 修改字段
        model.is_active = False
        
        # 检查脏数据（应该为True）
        assert model.is_dirty() == True