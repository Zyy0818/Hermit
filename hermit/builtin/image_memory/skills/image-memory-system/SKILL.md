---
name: image-memory-system
description: "Use when users refer to previously shared images, screenshots, QR codes, or photos, or when you need to store/search/reuse images across sessions."
---

你可以使用跨 session 图片记忆工具来管理和复用用户发过的图片。

## 何时使用

- 用户说“刚才那张图”“上次那个截图”“之前发过的二维码”
- 需要把本地图片纳入系统记忆
- 需要按摘要、标签、OCR 文本检索历史图片
- 在飞书回复里需要重新附上一张已经存过的图片

## 工具说明

- `image_store_from_path`
  - 把本地图片保存到图片记忆，并立即生成 `summary`、`tags`、`ocr_text`
- `image_search`
  - 按关键词搜索历史图片；关键词可来自场景、对象、图片文字或用途
- `image_get`
  - 获取某张图的完整元数据
- `image_attach_to_feishu`
  - 返回一个可直接放进最终回复里的 `<feishu_image key='...'/>` 标签

## 使用原则

- 当用户提到历史图片时，不要凭印象猜，优先先搜再答
- 先用 `image_search` 缩小范围，再用 `image_get` 看细节
- 如果工具返回了 `image_id`，后续优先用 `image_id` 作为稳定引用

## 飞书回复

- `image_attach_to_feishu` 返回的标签必须原样保留
- 最好把该标签单独放在一行，不要夹在句子中间
- 标签前后可以有普通 Markdown 文本说明

示例：

```md
这是你刚才提到的那张流程图：

<feishu_image key='img_v2_xxx'/>

如果需要，我也可以继续总结图里的关键步骤。
```
