# 実装ガイド (Implementation Guide)

## Python 規約

### 型定義

**組み込み型の使用**:
```python
# ✅ 良い例: 組み込み型とcollections.abcを使用
from collections.abc import Sequence

def process_items(items: Sequence[str]) -> dict[str, int]:
    """アイテムの出現回数をカウントする."""
    result: dict[str, int] = {}
    for item in items:
        result[item] = result.get(item, 0) + 1
    return result

# ❌ 悪い例: 古いtyping.Listを使用
from typing import List, Dict

def process_items(items: List[str]) -> Dict[str, int]:  # 非推奨
    pass
```

**型注釈の原則**:
```python
# ✅ 良い例: 明示的な型注釈
def calculate_total(prices: list[float]) -> float:
    """価格のリストから合計を計算する."""
    return sum(prices)

# ❌ 悪い例: 型注釈がない
def calculate_total(prices):  # Any型になる
    return sum(prices)
```

**Protocol vs dataclass**:
```python
from typing import Protocol
from dataclasses import dataclass

# Protocol: 構造的型付け（インターフェース）
class Task(Protocol):
    id: str
    title: str
    completed: bool

# dataclass: 具体的なデータクラス
@dataclass
class TaskImpl:
    id: str
    title: str
    completed: bool

# 拡張
@dataclass
class ExtendedTask(TaskImpl):
    priority: str

# 型エイリアス: ユニオン型、プリミティブ型など
from typing import TypeAlias, Literal

TaskStatus: TypeAlias = Literal["todo", "in_progress", "completed"]
TaskId: TypeAlias = str
Nullable: TypeAlias = T | None  # Python 3.10+
```

### 命名規則

**変数・関数**:
```python
# 変数: snake_case、名詞
user_name = "John"
task_list = []
is_completed = True

# 関数: snake_case、動詞で始める
def fetch_user_data() -> dict[str, Any]:
    """ユーザーデータを取得する."""
    pass

def validate_email(email: str) -> bool:
    """メールアドレスを検証する."""
    pass

def calculate_total_price(items: list[Item]) -> float:
    """合計金額を計算する."""
    pass

# Boolean: is, has, should, canで始める
is_valid = True
has_permission = False
should_retry = True
can_delete = False
```

**クラス・プロトコル**:
```python
# クラス: PascalCase、名詞
class TaskManager:
    """タスクを管理するクラス."""
    pass

class UserAuthenticationService:
    """ユーザー認証サービス."""
    pass

# Protocol: PascalCase
from typing import Protocol

class TaskRepository(Protocol):
    """タスクリポジトリのインターフェース."""
    pass

class UserProfile(Protocol):
    """ユーザープロフィールのインターフェース."""
    pass

# 型エイリアス: PascalCase
from typing import TypeAlias, Literal

TaskStatus: TypeAlias = Literal["todo", "in_progress", "completed"]
```

**定数**:
```python
# UPPER_SNAKE_CASE
from typing import Final

MAX_RETRY_COUNT: Final = 3
API_BASE_URL: Final = "https://api.example.com"
DEFAULT_TIMEOUT: Final = 5000

# 設定の場合はdataclassを推奨
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    max_retry_count: int = 3
    api_base_url: str = "https://api.example.com"
    default_timeout: int = 5000

CONFIG = Config()
```

**ファイル名**:
```python
# クラスファイル: snake_case
# task_service.py
# user_repository.py

# 関数・ユーティリティ: snake_case
# format_date.py
# validate_email.py

# パッケージ: snake_case
# task_management/
# user_profile/

# 定数: 通常のモジュール名 snake_case
# constants.py
# config.py
```

### 関数設計

**単一責務の原則**:
```python
from dataclasses import dataclass

@dataclass
class CartItem:
    price: float
    quantity: int

# ✅ 良い例: 単一の責務
def calculate_total_price(items: list[CartItem]) -> float:
    """カート内の商品の合計金額を計算する."""
    return sum(item.price * item.quantity for item in items)

def format_price(amount: float) -> str:
    """金額を日本円形式でフォーマットする."""
    return f"¥{amount:,.0f}"

# ❌ 悪い例: 複数の責務
def calculate_and_format_price(items: list[CartItem]) -> str:
    """計算とフォーマットの両方を行っている（非推奨）."""
    total = sum(item.price * item.quantity for item in items)
    return f"¥{total:,.0f}"
```

**関数の長さ**:
- 目標: 20行以内
- 推奨: 50行以内
- 100行以上: リファクタリングを検討

**パラメータの数**:
```python
from dataclasses import dataclass
from typing import Literal
from datetime import datetime

# ✅ 良い例: dataclassでまとめる
@dataclass
class CreateTaskOptions:
    title: str
    description: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    due_date: datetime | None = None

def create_task(options: CreateTaskOptions) -> Task:
    """タスクを作成する."""
    # 実装
    pass

# ❌ 悪い例: パラメータが多すぎる
def create_task(
    title: str,
    description: str,
    priority: str,
    due_date: datetime,
    tags: list[str],
    assignee: str,
) -> Task:
    """パラメータが多すぎる（非推奨）."""
    # 実装
    pass
```

### エラーハンドリング

**カスタムエラークラス**:
```python
from typing import Any

# エラークラスの定義
class ValidationError(Exception):
    """検証エラー.

    Args:
        message: エラーメッセージ
        field: エラーが発生したフィールド名
        value: エラーが発生した値
    """

    def __init__(self, message: str, field: str, value: Any) -> None:
        super().__init__(message)
        self.field = field
        self.value = value


class NotFoundError(Exception):
    """リソースが見つからないエラー.

    Args:
        resource: リソースの種類
        id: リソースのID
    """

    def __init__(self, resource: str, id: str) -> None:
        super().__init__(f"{resource} not found: {id}")
        self.resource = resource
        self.id = id


class DatabaseError(Exception):
    """データベースエラー.

    Args:
        message: エラーメッセージ
        cause: 原因となった例外
    """

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause
        if cause:
            self.__cause__ = cause
```

**エラーハンドリングパターン**:
```python
import logging

logger = logging.getLogger(__name__)

# ✅ 良い例: 適切なエラーハンドリング
async def get_task(id: str) -> Task:
    """タスクを取得する.

    Args:
        id: タスクID

    Returns:
        取得したタスク

    Raises:
        NotFoundError: タスクが見つからない場合
        DatabaseError: データベースエラーの場合
    """
    try:
        task = await repository.find_by_id(id)

        if not task:
            raise NotFoundError("Task", id)

        return task
    except NotFoundError as error:
        # 予期されるエラー: 適切に処理
        logger.warning(f"タスクが見つかりません: {id}")
        raise
    except Exception as error:
        # 予期しないエラー: ラップして上位に伝播
        raise DatabaseError("タスクの取得に失敗しました", error) from error


# ❌ 悪い例: エラーを無視
async def get_task(id: str) -> Task | None:
    """エラー情報が失われる（非推奨）."""
    try:
        return await repository.find_by_id(id)
    except Exception:
        return None  # エラー情報が失われる
```

**エラーメッセージ**:
```python
# ✅ 良い例: 具体的で解決策を示す
raise ValidationError(
    f"タイトルは1-200文字で入力してください。現在の文字数: {len(title)}",
    "title",
    title
)

# ❌ 悪い例: 曖昧で役に立たない
raise Exception("Invalid input")
```

### 非同期処理

**async/await の使用**:
```python
import logging

logger = logging.getLogger(__name__)

# ✅ 良い例: async/await
async def fetch_user_tasks(user_id: str) -> list[Task]:
    """ユーザーのタスクを取得する.

    Args:
        user_id: ユーザーID

    Returns:
        タスクのリスト

    Raises:
        Exception: タスク取得に失敗した場合
    """
    try:
        user = await user_repository.find_by_id(user_id)
        tasks = await task_repository.find_by_user_id(user.id)
        return tasks
    except Exception as error:
        logger.error("タスクの取得に失敗", exc_info=error)
        raise


# ❌ 悪い例: コールバックチェーン（Pythonでは通常使わない）
# Pythonでは常にasync/awaitを使用する
```

**並列処理**:
```python
import asyncio
from collections.abc import Sequence

# ✅ 良い例: asyncio.gatherで並列実行
async def fetch_multiple_users(ids: Sequence[str]) -> list[User]:
    """複数のユーザーを並列で取得する.

    Args:
        ids: ユーザーIDのリスト

    Returns:
        ユーザーのリスト
    """
    tasks = [user_repository.find_by_id(id) for id in ids]
    return await asyncio.gather(*tasks)


# ❌ 悪い例: 逐次実行
async def fetch_multiple_users(ids: Sequence[str]) -> list[User]:
    """逐次実行は遅い（非推奨）."""
    users: list[User] = []
    for id in ids:
        user = await user_repository.find_by_id(id)  # 遅い
        users.append(user)
    return users


# ✅ さらに良い例: エラーハンドリング付き並列処理
async def fetch_multiple_users_safe(ids: Sequence[str]) -> list[User | None]:
    """複数のユーザーを並列で取得する（エラーを無視）.

    Args:
        ids: ユーザーIDのリスト

    Returns:
        ユーザーのリスト（取得失敗時はNone）
    """
    tasks = [user_repository.find_by_id(id) for id in ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        result if not isinstance(result, Exception) else None
        for result in results
    ]
```

## コメント規約

### ドキュメントコメント

**Googleスタイルdocstring**:
```python
async def create_task(data: CreateTaskData) -> Task:
    """タスクを作成する.

    Args:
        data: 作成するタスクのデータ

    Returns:
        作成されたタスク

    Raises:
        ValidationError: データが不正な場合
        DatabaseError: データベースエラーの場合

    Examples:
        >>> task = await create_task(
        ...     CreateTaskData(title="新しいタスク", priority="high")
        ... )
        >>> task.title
        '新しいタスク'
    """
    # 実装
    pass
```

### インラインコメント

**良いコメント**:
```python
# ✅ 理由を説明
# キャッシュを無効化して最新データを取得
cache.clear()

# ✅ 複雑なロジックを説明
# Kadaneのアルゴリズムで最大部分配列和を計算
# 時間計算量: O(n)
max_so_far = arr[0]
max_ending_here = arr[0]

# ✅ TODO・FIXMEを活用
# TODO: キャッシュ機能を実装 (Issue #123)
# FIXME: 大量データでパフォーマンス劣化 (Issue #456)
# HACK: 一時的な回避策、後でリファクタリング必要
```

**悪いコメント**:
```python
# ❌ コードの内容を繰り返すだけ
# iを1増やす
i += 1

# ❌ 古い情報
# このコードは2020年に追加された (不要な情報)

# ❌ コメントアウトされたコード
# old_implementation = lambda: ...  # 削除すべき
```

## セキュリティ

### 入力検証

```python
import re
from typing import Any

# ✅ 良い例: 厳密な検証
def validate_email(email: Any) -> None:
    """メールアドレスを検証する.

    Args:
        email: 検証するメールアドレス

    Raises:
        ValidationError: メールアドレスが不正な場合
    """
    if not email or not isinstance(email, str):
        raise ValidationError("メールアドレスは必須です", "email", email)

    email_regex = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    if not email_regex.match(email):
        raise ValidationError("メールアドレスの形式が不正です", "email", email)

    if len(email) > 254:
        raise ValidationError("メールアドレスが長すぎます", "email", email)


# ❌ 悪い例: 検証なし
def validate_email(email: str) -> None:
    """検証なし（非推奨）."""
    pass
```

### 機密情報の管理

```python
import os

# ✅ 良い例: 環境変数から読み込み
api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("API_KEY環境変数が設定されていません")

# より良い例: pydantic-settingsを使用
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """アプリケーション設定."""

    api_key: str
    database_url: str
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# ❌ 悪い例: ハードコード
api_key = "sk-1234567890abcdef"  # 絶対にしない！
```

## パフォーマンス

### データ構造の選択

```python
from typing import TypeVar

T = TypeVar("T")

# ✅ 良い例: dictで O(1) アクセス
user_map = {user.id: user for user in users}
user = user_map.get(user_id)  # O(1)

# ❌ 悪い例: リストで O(n) 検索
user = next((u for u in users if u.id == user_id), None)  # O(n)

# ✅ さらに良い例: setで O(1) 検索（存在確認のみ）
user_ids = {user.id for user in users}
exists = user_id in user_ids  # O(1)
```

### ループの最適化

```python
# ✅ 良い例: 不要な計算をループの外に
length = len(items)
for i in range(length):
    process(items[i])

# ❌ 悪い例: 毎回lengthを計算（実際にはPythonでは問題ない）
for i in range(len(items)):
    process(items[i])

# ✅ より良い: 直接イテレート
for item in items:
    process(item)

# ✅ インデックスも必要な場合: enumerate
for i, item in enumerate(items):
    process(item, i)
```

### メモ化

```python
from functools import lru_cache
from typing import Any

# ✅ 良い例: functools.lru_cacheを使用
@lru_cache(maxsize=128)
def expensive_calculation(input: str) -> Any:
    """計算結果をキャッシュする.

    Args:
        input: 入力値

    Returns:
        計算結果
    """
    # 重い計算
    result = ...
    return result


# 手動でキャッシュを実装する場合
cache: dict[str, Any] = {}

def expensive_calculation_manual(input: str) -> Any:
    """手動でキャッシュを実装する例.

    Args:
        input: 入力値

    Returns:
        計算結果
    """
    if input in cache:
        return cache[input]

    # 重い計算
    result = ...
    cache[input] = result
    return result
```

## テストコード

### テストの構造 (Given-When-Then)

```python
import pytest
from datetime import datetime
from unittest.mock import Mock

class TestTaskService:
    """TaskServiceのテスト."""

    @pytest.mark.asyncio
    async def test_create_task_with_valid_data(
        self,
        mock_repository: Mock
    ) -> None:
        """正常なデータでタスクを作成できる."""
        # Given: 準備
        service = TaskService(mock_repository)
        task_data = CreateTaskData(
            title="テストタスク",
            description="テスト用の説明",
        )

        # When: 実行
        result = await service.create(task_data)

        # Then: 検証
        assert result is not None
        assert result.id is not None
        assert result.title == "テストタスク"
        assert result.description == "テスト用の説明"
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_task_with_empty_title_raises_validation_error(
        self,
        mock_repository: Mock
    ) -> None:
        """タイトルが空の場合ValidationErrorをスローする."""
        # Given: 準備
        service = TaskService(mock_repository)
        invalid_data = CreateTaskData(title="")

        # When/Then: 実行と検証
        with pytest.raises(ValidationError):
            await service.create(invalid_data)
```

### モックの作成

```python
from unittest.mock import Mock, AsyncMock
import pytest
from typing import Iterator

# ✅ 良い例: Protocolに基づくモック
@pytest.fixture
def mock_repository() -> Iterator[Mock]:
    """モックリポジトリのフィクスチャ."""
    mock = Mock(spec=TaskRepository)
    mock.save = AsyncMock()
    mock.find_by_id = AsyncMock()
    mock.find_all = AsyncMock()
    mock.delete = AsyncMock()
    yield mock

# テストごとに動作を設定
@pytest.fixture
def mock_repository_with_data(mock_repository: Mock, mock_task: Task) -> Mock:
    """データを持つモックリポジトリ."""
    async def find_by_id_impl(id: str) -> Task | None:
        if id == "existing-id":
            return mock_task
        return None

    mock_repository.find_by_id.side_effect = find_by_id_impl
    return mock_repository


# より詳細なモック例
@pytest.fixture
def mock_task() -> Task:
    """テスト用のタスク."""
    return Task(
        id="test-id",
        title="テストタスク",
        description="テスト用の説明",
        created_at=datetime.now(),
    )
```

## リファクタリング

### マジックナンバーの排除

```python
import asyncio
from typing import Final

# ✅ 良い例: 定数を定義
MAX_RETRY_COUNT: Final = 3
RETRY_DELAY_MS: Final = 1000

async def fetch_with_retry() -> Any:
    """リトライ機能付きでデータを取得する."""
    for i in range(MAX_RETRY_COUNT):
        try:
            return await fetch_data()
        except Exception as error:
            if i < MAX_RETRY_COUNT - 1:
                await asyncio.sleep(RETRY_DELAY_MS / 1000)
            else:
                raise


# ❌ 悪い例: マジックナンバー
async def fetch_with_retry_bad() -> Any:
    """マジックナンバーを使用（非推奨）."""
    for i in range(3):  # 3は何？
        try:
            return await fetch_data()
        except Exception:
            if i < 2:
                await asyncio.sleep(1)  # 1000msのこと？
```

### 関数の抽出

```python
from dataclasses import dataclass

@dataclass
class Order:
    items: list[OrderItem]
    total: float = 0.0
    coupon: Coupon | None = None

# ✅ 良い例: 関数を抽出
def process_order(order: Order) -> None:
    """注文を処理する.

    Args:
        order: 処理する注文
    """
    validate_order(order)
    calculate_total(order)
    apply_discounts(order)
    save_order(order)


def validate_order(order: Order) -> None:
    """注文を検証する.

    Args:
        order: 検証する注文

    Raises:
        ValidationError: 商品が選択されていない場合
    """
    if not order.items:
        raise ValidationError("商品が選択されていません", "items", order.items)


def calculate_total(order: Order) -> None:
    """合計金額を計算する.

    Args:
        order: 計算対象の注文
    """
    order.total = sum(item.price * item.quantity for item in order.items)


def apply_discounts(order: Order) -> None:
    """割引を適用する.

    Args:
        order: 割引を適用する注文
    """
    if order.coupon:
        order.total -= order.total * order.coupon.discount_rate


def save_order(order: Order) -> None:
    """注文を保存する.

    Args:
        order: 保存する注文
    """
    repository.save(order)


# ❌ 悪い例: 長い関数
def process_order_bad(order: Order) -> None:
    """長すぎる関数（非推奨）."""
    if not order.items:
        raise ValidationError("商品が選択されていません", "items", order.items)

    order.total = sum(item.price * item.quantity for item in order.items)

    if order.coupon:
        order.total -= order.total * order.coupon.discount_rate

    repository.save(order)
```

## チェックリスト

実装完了前に確認:

### コード品質
- [ ] 命名が明確で一貫している（snake_case、PascalCase）
- [ ] 関数が単一の責務を持っている
- [ ] マジックナンバーがない（定数化されている）
- [ ] 型ヒントが適切に記載されている（Python 3.10+スタイル）
- [ ] エラーハンドリングが実装されている（カスタム例外使用）

### セキュリティ
- [ ] 入力検証が実装されている
- [ ] 機密情報がハードコードされていない（環境変数使用）
- [ ] SQLインジェクション対策がされている（パラメータ化クエリ）
- [ ] 型検証が実装されている（isinstance チェック）

### パフォーマンス
- [ ] 適切なデータ構造を使用している（dict, set など）
- [ ] 不要な計算を避けている
- [ ] ループが最適化されている（内包表記、ジェネレータ活用）
- [ ] メモ化が適用されている（必要な場合）

### テスト
- [ ] pytestユニットテストが書かれている
- [ ] テストがパスする（pytest 実行）
- [ ] エッジケースがカバーされている
- [ ] 非同期テストが適切に実装されている（@pytest.mark.asyncio）
- [ ] モックが適切に使用されている

### ドキュメント
- [ ] 関数・クラスにGoogleスタイルdocstringがある
- [ ] 複雑なロジックにコメントがある
- [ ] TODOやFIXMEが記載されている（該当する場合）
- [ ] 型ヒントが完全に記載されている

### ツール
- [ ] ruff/flake8のLintエラーがない
- [ ] mypyの型チェックがパスする（--strict モード）
- [ ] blackでフォーマットが統一されている
- [ ] isortでimportが整理されている
