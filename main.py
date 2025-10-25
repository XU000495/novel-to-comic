from flask import Flask, request, jsonify, send_file
import openai
import requests
import json
import os
from PIL import Image, ImageDraw, ImageFont
import io
import base64

app = Flask(__name__)

# 配置API密钥
openai.api_key = os.getenv("OPENAI_API_KEY")


class NovelToComicConverter:
    def __init__(self):
        self.scene_cache = {}
        self.character_cache = {}

    def analyze_novel_content(self, novel_text):
        """使用GPT-4分析小说内容，提取关键元素"""
        prompt = f"""
        请分析以下小说内容，并提取以下信息：
        1. 主要场景描述
        2. 主要角色及其特征
        3. 关键情节转折点
        4. 对话内容
        5. 情感氛围

        小说内容：
        {novel_text}

        请以JSON格式返回分析结果，包含以下字段：
        - scenes: 场景列表，每个场景包含描述、氛围、重要性
        - characters: 角色列表，每个角色包含名称、外貌特征、情绪
        - dialogues: 对话列表，每个对话包含说话者、内容、情绪
        - plot_points: 关键情节点列表
        """

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "你是一个专业的小说分析师，擅长提取视觉元素。"},
                {"role": "user", "content": prompt}
            ]
        )

        analysis = json.loads(response.choices[0].message.content)
        return analysis

    def plan_storyboard(self, analysis):
        """规划漫画分镜"""
        scenes = analysis["scenes"]
        dialogues = analysis["dialogues"]

        storyboard = []
        current_panel = 1

        # 简单的分镜规划逻辑 - 实际应用中需要更复杂的算法
        for i, scene in enumerate(scenes):
            # 决定每个场景需要多少分镜
            importance = scene.get("importance", 1)
            panels_for_scene = min(importance, 3)  # 最多3个分镜 per 场景

            for j in range(panels_for_scene):
                panel = {
                    "panel_number": current_panel,
                    "scene_description": scene["description"],
                    "atmosphere": scene["atmosphere"],
                    "characters_in_scene": self._get_characters_in_scene(scene, analysis["characters"]),
                    "dialogue": self._get_relevant_dialogue(i, j, dialogues, panels_for_scene)
                }
                storyboard.append(panel)
                current_panel += 1

        return storyboard

    def generate_comic_panel(self, panel_info, style="anime"):
        """生成单个漫画分镜"""
        # 创建详细的图像描述
        image_prompt = self._create_image_prompt(panel_info, style)

        # 使用DALL-E 3生成图像
        response = openai.Image.create(
            model="dall-e-3",
            prompt=image_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url
        image_response = requests.get(image_url)
        panel_image = Image.open(io.BytesIO(image_response.content))

        # 添加对话气泡（如果有对话）
        if panel_info.get("dialogue"):
            panel_image = self._add_speech_bubble(panel_image, panel_info["dialogue"])

        return panel_image

    def _create_image_prompt(self, panel_info, style):
        """创建详细的图像生成提示"""
        base_style = {
            "anime": "日本动漫风格，色彩鲜艳，线条清晰",
            "american": "美式漫画风格，粗线条，高对比度",
            "watercolor": "水彩画风格，柔和色彩，艺术感强"
        }

        prompt = f"""
        {base_style.get(style, "日本动漫风格")}，
        漫画分镜，{panel_info['atmosphere']}氛围，
        场景：{panel_info['scene_description']}，
        """

        if panel_info.get('characters_in_scene'):
            characters_desc = "，".join([f"{char['name']}：{char.get('appearance', '')}"
                                        for char in panel_info['characters_in_scene']])
            prompt += f"角色：{characters_desc}，"

        prompt += "高质量漫画艺术，专业构图，动态感强"

        return prompt

    def _add_speech_bubble(self, image, dialogue):
        """在图像上添加对话气泡"""
        draw = ImageDraw.Draw(image)

        # 简单的气泡实现 - 实际应用需要更精细的实现
        bubble_width = 300
        bubble_height = 100
        bubble_x = 50
        bubble_y = image.height - 150

        # 绘制气泡
        draw.rounded_rectangle([bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height],
                               radius=20, fill="white", outline="black", width=3)

        # 添加对话文本
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()

        text = f"{dialogue.get('speaker', '')}: {dialogue.get('content', '')}"
        # 简单的文本换行
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= bubble_width - 20:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        # 绘制文本
        text_y = bubble_y + 10
        for line in lines[:3]:  # 最多显示3行
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = bubble_x + (bubble_width - text_width) / 2
            draw.text((text_x, text_y), line, fill="black", font=font)
            text_y += 20

        return image

    def _get_characters_in_scene(self, scene, all_characters):
        """获取场景中的角色"""
        # 简化实现 - 实际应用中需要更精确的角色场景匹配
        return all_characters[:2]  # 假设前两个角色在场景中

    def _get_relevant_dialogue(self, scene_index, panel_index, dialogues, panels_in_scene):
        """获取相关的对话"""
        if not dialogues:
            return None

        # 简单的对话分配逻辑
        dialogue_index = scene_index * panels_in_scene + panel_index
        if dialogue_index < len(dialogues):
            return dialogues[dialogue_index]
        return None


@app.route('/generate-comic', methods=['POST'])
def generate_comic():
    data = request.json
    novel_text = data.get('novel_text', '')
    style = data.get('style', 'anime')

    if not novel_text:
        return jsonify({"error": "没有提供小说文本"}), 400

    converter = NovelToComicConverter()

    # 分析小说内容
    analysis = converter.analyze_novel_content(novel_text)

    # 规划分镜
    storyboard = converter.plan_storyboard(analysis)

    # 生成漫画图像
    comic_pages = []
    for i, panel in enumerate(storyboard):
        panel_image = converter.generate_comic_panel(panel, style)

        # 转换为base64用于返回
        buffered = io.BytesIO()
        panel_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        comic_pages.append({
            "panel_number": panel["panel_number"],
            "image": f"data:image/png;base64,{img_str}",
            "description": panel["scene_description"]
        })

    return jsonify({
        "analysis": analysis,
        "storyboard": storyboard,
        "comic_pages": comic_pages
    })


if __name__ == '__main__':
    app.run(debug=True)