import streamlit as st
import groq
import os
from pathlib import Path
import tempfile
from audio_recorder_streamlit import audio_recorder
from pydub import AudioSegment
import io
from llmlingua import PromptCompressor


class Assistant:
	def __init__(self):
		self.api_key = "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"
		self.client = groq.Groq(api_key=self.api_key)
		self.meta_llm = "llama-3.1-70b-versatile"
		self.task_llm = "llama-3.1-70b-versatile"

		try:
			with open("meta_prompt.md", "r", encoding="utf-8") as file:
				self.meta_prompt = file.read()
		except Exception as e:
			st.error(f"Error loading meta_prompt.md: {str(e)}")
			self.meta_prompt = ""

	def transcribe_audio(self, audio_bytes):
		temp_path = None
		try:
			audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
			temp_path = os.path.join(tempfile.gettempdir(), f'audio_{os.urandom(8).hex()}.wav')
			audio.export(temp_path, format="wav", parameters=["-acodec", "pcm_s16le", "-ar", "16000"])

			with open(temp_path, 'rb') as audio_file:
				response = self.client.audio.transcriptions.create(
					model="whisper-large-v3",
					file=audio_file
				)
			return response.text

		except Exception as e:
			st.error(f"Error transcribing audio: {str(e)}")
			return None
		finally:
			if temp_path and os.path.exists(temp_path):
				try:
					os.remove(temp_path)
				except Exception as e:
					st.warning(f"Could not remove temporary file: {str(e)}")

	def generate_system_prompt(self, user_prompt):
		try:
			response = self.client.chat.completions.create(
				model=self.meta_llm,
				messages=[
					{"role": "system", "content": self.meta_prompt},
					{"role": "user", "content": f"Generate an appropriate system prompt for an LLM to handle this user request/task: {user_prompt}"},
				],
				temperature=0.2,
				top_p=0.2,
			)
			return response.choices[0].message.content
		except Exception as e:
			st.error(f"Error generating system prompt: {str(e)}")
			return None

	def execute_task(self, system_prompt, user_prompt, context_data=None):
		try:
			final_prompt = f"USER_PROMPT = {user_prompt}"
			if context_data:
				final_prompt += f"\nCONTEXT_INFO = {context_data}"

			response = self.client.chat.completions.create(
				model=self.task_llm,
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": final_prompt},
				],
				temperature=0.2,
				top_p=0.2
			)
			return response.choices[0].message.content
		except Exception as e:
			st.error(f"Error executing task: {str(e)}")
			return None


def count_tokens(text):
	try:
		tokenizer = st.session_state.compressor.tokenizer
		tokens = tokenizer.encode(text)
		return len(tokens)
	except Exception as e:
		st.error(f"Error counting tokens: {str(e)}")
		return 0


def compress_text(text, compression_rate):
	try:
		results = st.session_state.compressor.compress_prompt_llmlingua2(
			text,
			rate=compression_rate,
			force_tokens=['\n', '.', '!', '?', ','],
			chunk_end_tokens=['.', '\n'],
			return_word_label=True,
			drop_consecutive=True,
		)
		compressed_text = results['compressed_prompt']
		st.session_state.original_tokens = count_tokens(text)
		st.session_state.current_tokens = count_tokens(compressed_text)
		return compressed_text
	except Exception as e:
		st.error(f"Error compressing text: {str(e)}")
		return text


def load_context(file_path):
	try:
		with open(file_path, "r", encoding="utf-8") as file:
			content = file.read()
			st.session_state.original_context = content
			st.session_state.context_data = content
			st.session_state.context_loaded = True
			st.session_state.original_tokens = count_tokens(content)
			st.session_state.current_tokens = st.session_state.original_tokens
	except Exception as e:
		st.error(f"Error loading context file: {str(e)}")


def init_session_state():
	defaults = {
		"context_loaded": False,
		"context_data": None,
		"original_context": None,
		"original_tokens": 0,
		"current_tokens": 0,
		"input_mode": "type",
		"compressor": PromptCompressor(
			model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
			use_llmlingua2=True
		)
	}
	for key, value in defaults.items():
		if key not in st.session_state:
			st.session_state[key] = value


def display_token_info():
	st.markdown(f"**Original Token Count:** {st.session_state.original_tokens}")
	if st.session_state.current_tokens != st.session_state.original_tokens:
		compression_percentage = ((st.session_state.original_tokens - st.session_state.current_tokens)
								/ st.session_state.original_tokens * 100)
		st.markdown(f"**Current Token Count:** {st.session_state.current_tokens} "
				   f"({compression_percentage:.1f}% reduction)")


def main():
	st.set_page_config(page_title="AI Assistant Demo", layout="wide")
	init_session_state()

	st.title("🤖 AI Assistant Demo")
	st.markdown(
		"""
		This demo showcases an AI assistant that can generate system prompts and execute tasks based on user inputs.
		Enter your prompt below to get started!
		"""
	)

	assistant = Assistant()

	with st.expander("Context Management"):
		col1, col2, col3 = st.columns([1, 1, 1])
		with col1:
			if not st.session_state.context_loaded:
				if st.button("Load Github Dummy Data"):
					load_context("context_gh.md")
					st.rerun()
				if st.button("Load Slack Dummy Data"):
					load_context("context_s.md")
					st.rerun()

		with col3:
			if st.session_state.context_loaded:
				if st.button("Clear Context"):
					for key in ["context_data", "original_context", "original_tokens",
							  "current_tokens", "context_loaded"]:
						st.session_state[key] = None if key != "context_loaded" else False
					st.rerun()

		if st.session_state.context_loaded:
			st.markdown("---")
			st.subheader("Text Compression")

			if st.session_state.context_data:
				st.session_state.current_tokens = count_tokens(st.session_state.context_data)

			display_token_info()

			compression_rate = st.slider(
				"Compression Ratio",
				min_value=0.1, max_value=0.9, value=0.5, step=0.1,
				help="Higher values mean more compression (e.g., 0.9 will compress more than 0.1)"
			)

			col1, col2 = st.columns(2)
			with col1:
				if st.button("Compress Text", key="compress_btn"):
					with st.spinner("Compressing text..."):
						compressed = compress_text(st.session_state.original_context, compression_rate)
						st.session_state.context_data = compressed
						st.session_state.current_tokens = count_tokens(compressed)
						st.rerun()

			with col2:
				if st.button("Reset to Original"):
					st.session_state.context_data = st.session_state.original_context
					st.session_state.current_tokens = st.session_state.original_tokens
					st.rerun()

			st.markdown("---")
			st.subheader("Current Context")
			st.code(st.session_state.context_data, language="markdown")

	st.subheader("Choose Input Method")
	input_mode = st.radio("Select input method:", ("Type", "Speak"), horizontal=True)
	st.session_state.input_mode = input_mode.lower()

	st.subheader("Enter Your Prompt")
	user_prompt = ""

	if st.session_state.input_mode == "type":
		user_prompt = st.text_area(
			"What would you like the AI to do?",
			placeholder="Enter your prompt here...",
			height=100,
		)
	else:
		st.write("Click the button below and speak your prompt:")
		audio_bytes = audio_recorder()
		if audio_bytes:
			with st.spinner("Transcribing your speech..."):
				transcribed_text = assistant.transcribe_audio(audio_bytes)
				if transcribed_text:
					user_prompt = transcribed_text
					st.markdown("### Transcribed Text")
					st.code(transcribed_text, language="markdown")

	col1, col2 = st.columns([1, 1])
	with col1:
		generate_prompt = st.button("Generate System Prompt", type="primary")
	with col2:
		execute_task = st.button("Execute Task", type="primary")

	st.subheader("System Prompt")
	if generate_prompt and user_prompt:
		with st.spinner("Generating system prompt..."):
			system_prompt = assistant.generate_system_prompt(user_prompt)
			if system_prompt:
				st.session_state["system_prompt"] = system_prompt
				st.code(system_prompt, language="markdown")
	elif "system_prompt" in st.session_state:
		st.code(st.session_state["system_prompt"], language="markdown")
	else:
		st.info("Click 'Generate System Prompt' to see the system prompt here.")

	st.subheader("Task Output")
	if execute_task and "system_prompt" in st.session_state:
		with st.spinner("Executing task..."):
			output = assistant.execute_task(
				st.session_state["system_prompt"],
				user_prompt,
				st.session_state.context_data if st.session_state.context_loaded else None
			)
			if output:
				st.session_state["task_output"] = output
				st.markdown(output)
	elif "task_output" in st.session_state:
		st.markdown(st.session_state["task_output"])
	else:
		st.info("Click 'Execute Task' to see the output here.")


if __name__ == "__main__":
	main()