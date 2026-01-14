import pytest
from fastapi import HTTPException
# Добавляем импорт User, чтобы SQLAlchemy видела все связанные модели
from user_service.models import Role, RoleAccess, User

# Фикстуры db_session и rbac_service теперь приходят из conftest.py автоматически

@pytest.mark.asyncio
async def test_create_role_success(rbac_service, db_session):
    """Успешное создание новой роли в тестовой БД."""
    role_name = "new_admin"
    new_role = await rbac_service.create_role(role_name, can_write_all=True)
    
    assert new_role.name == role_name
    assert new_role.can_write_all is True
    
    # Проверяем, что роль действительно в базе (интеграционная проверка)
    from sqlalchemy import select
    stmt = select(Role).where(Role.name == role_name)
    result = await db_session.execute(stmt)
    assert result.scalars().first() is not None

@pytest.mark.asyncio
async def test_create_role_already_exists(rbac_service, db_session):
    """Ошибка при попытке создать роль с уже существующим именем."""
    role_name = "duplicate_role"
    await rbac_service.create_role(role_name)
    
    with pytest.raises(HTTPException) as exc:
        await rbac_service.create_role(role_name)
    
    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail

@pytest.mark.asyncio
async def test_get_role_by_name_success(rbac_service, db_session):
    """Получение существующей роли по её имени."""
    role_name = "manager"
    await rbac_service.create_role(role_name)
    
    result = await rbac_service.get_role_by_name(role_name)
    assert result.name == role_name

@pytest.mark.asyncio
async def test_get_role_by_name_not_found(rbac_service):
    """Ошибка 404 при поиске несуществующей роли."""
    with pytest.raises(HTTPException) as exc:
        await rbac_service.get_role_by_name("non_existent")
    
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_set_role_access_upsert(rbac_service, db_session):
    """
    Проверка логики UPSERT (создание или обновление прав).
    Использует реальную SQLite базу для проверки конфликтов.
    """
    role_name = "editor"
    await rbac_service.create_role(role_name)
    
    # 1. Создаем права (INSERT)
    role = await rbac_service.set_role_access(
        role_name, "news", can_read=True, can_write=False
    )
    
    # Принудительно заставляем сессию перечитать объект из БД,
    # чтобы увидеть изменения в access_list
    await db_session.refresh(role, ["access_list"])
    
    assert len(role.access_list) == 1
    assert role.access_list[0].can_read is True
    assert role.access_list[0].can_write is False

    # 2. Обновляем те же самые права (UPDATE через ON CONFLICT)
    updated_role = await rbac_service.set_role_access(
        role_name, "news", can_read=True, can_write=True
    )
    
    # Повторно обновляем связи
    await db_session.refresh(updated_role, ["access_list"])
    
    # Количество записей в access_list не должно измениться
    assert len(updated_role.access_list) == 1
    assert updated_role.access_list[0].can_write is True

@pytest.mark.asyncio
async def test_delete_role(rbac_service, db_session):
    """Проверка удаления роли и связанных с ней данных."""
    role_name = "temporary"
    await rbac_service.create_role(role_name)
    
    await rbac_service.delete_role(role_name)
    
    with pytest.raises(HTTPException) as exc:
        await rbac_service.get_role_by_name(role_name)
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_get_all_roles(rbac_service):
    """Проверка получения списка всех ролей."""
    await rbac_service.create_role("role1")
    await rbac_service.create_role("role2")
    
    roles = await rbac_service.get_all_roles()
    assert len(roles) >= 2