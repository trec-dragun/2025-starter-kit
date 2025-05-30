import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from pydantic import BaseModel


load_dotenv()


class Sentences(BaseModel):
    sentences: list[str]


class ReportShortener:
    def __init__(self):
        self.report_shortener = AzureOpenAI(
            api_version=os.getenv('OPENAI_API_VERSION'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY')
        )
    
    def shorten_report(self, sentences: str, word_count: int):
        target_words = 240  # Aim slightly below 250 to ensure we hit the target
        words_to_remove = max(word_count - target_words, 20)
        system_prompt = f'''\
You are a professional fact-checker who has written a report comprising sentences that provide background and context to help readers assess the trustworthiness of a news article. The report exceeds the 250-word limit and must be shortened. The number of words are counted by splitting the sentence by white space characters. The current report has {word_count} words. You MUST remove at least {words_to_remove} words to get the report down to approximately {target_words} words.

Your task is to aggressively condense the report while:
- Preserving the core meaning and factual accuracy
- Maintaining the same number of sentences
- Ensuring each sentence remains coherent and informative
- Removing all unnecessary words, redundant phrases, and verbose expressions

Be decisive in your editing: remove filler words, simplify complex phrases, use shorter synonyms, and eliminate redundancy. Your goal is to achieve the target word reduction in one pass.'''
        user_input = f'The report is shown below. \n{sentences}'
        completion = self.report_shortener.beta.chat.completions.parse(
            model='gpt-4.1',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_input}
            ],
            temperature=0,
            presence_penalty=0,
            frequency_penalty=0,
            response_format=Sentences,
        )
        return completion.choices[0].message.parsed


def main():
    team_id = 'dragun-organizers'
    run_id_prefix = 'dragun-organizers-starter-kit'

    target_article_ids = []
    with open('./data/trec-2025-dragun-topics.jsonl', 'r', encoding='utf-8') as f_in:
        for line in f_in:
            target_article_ids.append(json.loads(line.strip())['docid'])

    with open('output/tracking_data.json', 'r', encoding='utf-8') as f_in:
        tracking_data = json.load(f_in)
    
    task1_output = ''
    task2_output = []
    report_shortener = ReportShortener()

    for article_id in target_article_ids:
        article_data = tracking_data[article_id]
        for i in range(len(article_data['question_generation'])):
            question = article_data['question_generation'][f'question_{i+1}']['question']
            task1_output += f'{article_id}\t{team_id}\t{run_id_prefix}-task-1\t{i+1}\t{question}\n'

        sentences = []
        original_word_count = 0
        responses = []
        for i in range(len(article_data['report_generation'])):
            sentence = article_data['report_generation'][f'sentence_{i+1}']['sentence']
            sentences.append(sentence)
            original_word_count += len(sentence.split())
        if original_word_count > 250:
            print(f'[INFO] {article_id} has {original_word_count} words in the report.')
            new_word_count = original_word_count
            new_sentences = sentences.copy()
            for i in range(5):
                if new_word_count <= 250:
                    break
                else:
                    print(f'\t[INFO] {article_id} has {new_word_count} words in the report. Shortening in iteration {i+1} ...')
                    response = report_shortener.shorten_report(json.dumps(new_sentences, indent=4), new_word_count)
                    new_sentences = response.sentences
                    new_word_count = sum(len(sentence.split()) for sentence in new_sentences)
            assert len(new_sentences) == len(sentences)
            print(f'\t[INFO] {article_id} now has {new_word_count} words in the report after shortening.')
            for i in range(len(sentences)):
                responses.append({'text': new_sentences[i], 'citations': article_data['report_generation'][f'sentence_{i+1}']['citations']})
        else:
            for i in range(len(article_data['report_generation'])):
                responses.append({'text': article_data['report_generation'][f'sentence_{i+1}']['sentence'], 
                                  'citations': article_data['report_generation'][f'sentence_{i+1}']['citations']})
        
        task2_output.append({
            'metadata': {
                'team_id': team_id,
                'run_id': f'{run_id_prefix}-task-2',
                'topic_id': article_id,
                'type': 'automatic',
                'use_starter_kit': 1
            },
            'responses': responses
        })

    task1_output = task1_output.strip()

    with open(f'output/{run_id_prefix}-task-1', 'w', encoding='utf-8') as f_out:
        f_out.write(task1_output)

    with open(f'output/{run_id_prefix}-task-2', 'w', encoding='utf-8') as f_out:
        for item in task2_output:
            f_out.write(json.dumps(item) + '\n')


if __name__ == "__main__":
    main() 