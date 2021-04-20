# flyer-ocr
チラシOCR

## 概要
スーパー公式サイトからチラシを取得し、OCRしてキーワード設定した商品がヒットしたらSlackに通知します

## 使用しているもの
PDF→JPG変換：pdf2imageを使用しています  
→「Poppler」というフリーのPDFコマンドラインツールを背後で用いるため、Popplerをlib/popplerにダウンロードしています

OCR：Google Vision APIを使用しています
