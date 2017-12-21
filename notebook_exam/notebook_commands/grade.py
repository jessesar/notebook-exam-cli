import click
import subprocess
import json
import pandas as pd
import numpy as np
import os
from subprocess import call
from tabulate import tabulate

from colorama import Fore, Back, Style

from notebook_client import Client, download_file
from random import shuffle
from glob import glob

from shutil import copyfile

from os.path import expanduser
home = expanduser('~')

with open(home +'/.notebook-exam-password') as f:
	interface_password = f.read()
	
def execute(c):
    call(c.split())

@click.command('collect-submissions')
@click.argument('exam_name')
def collect_submissions(exam_name):
    print '-- Generating submissions file...'
    
    c = Client(password=interface_password)
    c.execute('/var/uva/scripts/collect_submissions %s' % exam_name)
    
    print '-- Downloading submissions file from hub...'
    c = Client(password=interface_password)
    download_file(c, 'submissions.zip')
    
    execute('unzip -q submissions.zip -d all-submissions/')
    execute('rm -f submissions.zip')

    print
    print Fore.GREEN + ('Exam submissions for exam "%s" have been saved to all-submissions/.' % exam_name) + Style.RESET_ALL
    
@click.command('divide-submissions')
@click.argument('submissions_folder')
@click.argument('graders')
def divide_submissions(submissions_folder, graders):
    graders = graders.split(',')
    
    notebooks = glob('%s/*.ipynb' % submissions_folder)
    shuffle(notebooks)
    
    chunks = [ list(l) for l in np.array_split(notebooks, len(graders)) ]
    notebook_by_grader = zip(graders, chunks)
    
    if os.path.exists('%s/student-answers.csv' % submissions_folder):
        answers = pd.read_csv('%s/student-answers.csv' % submissions_folder, dtype={ 'student': str })
        
        answers.set_index(['student', 'question'], inplace=True)
        answers.sort_index(level=0, inplace=True)
    else:
        answers = None

    os.makedirs('divided-submissions')
    for grader, notebooks in notebook_by_grader:
        os.makedirs('divided-submissions/%s' % grader)
        
        for notebook in notebooks:
            copyfile(notebook, 'divided-submissions/%s/%s' % (grader, os.path.basename(notebook)))
            
        student_ids = [ os.path.basename(notebook).split('.')[0].split('_')[-1] for notebook in notebooks ]
        
        if answers is not None:
            answers_subset = answers.loc[student_ids]
            
            answers_subset.to_csv('divided-submissions/%s/student-answers.csv' % grader, encoding='utf8')
          
    print Fore.GREEN + ('Exam submissions have been divided among: %s' % ', '.join(graders))
    print 'Their folders can be found in submissions/.' + Style.RESET_ALL
    
@click.command('merge-results')
@click.argument('submissions_folder')
def merge_results(submissions_folder):
    results_files = glob('%s/*/student-answers.csv' % submissions_folder)
    
    results_dfs = [ pd.read_csv(f, dtype={ 'student': str }).set_index(['student', 'question']) for f in results_files ]
    all_results = pd.concat(results_dfs).sort_index(level=0)
            
    all_results.to_csv('all-results.csv', encoding='utf8')
    
    print Fore.GREEN + ('Exam results have been merged and saved to all-results.csv.') + Style.RESET_ALL
    
@click.command('calculate-grades')
@click.argument('results_file')
@click.argument('maximum_score')
def calculate_grades(results_file, maximum_score):
    results = pd.read_csv(results_file, dtype={ 'student': str })
    
    grades = (results.groupby('student').sum() / float(maximum_score)) * 10
    grades = grades.fillna(0)
    
    grades.to_csv('grades.csv')
    
    print 'Grades are calculated using the formula: (score / max) * 10.'
    print Fore.GREEN + ('Grades have been calculated and saved to grades.csv.') + Style.RESET_ALL
    
@click.command('auto-score')
@click.argument('submissions_folder')
@click.argument('answer_model_file')
def auto_score(submissions_folder, answer_model_file):
    def check_answer(row):
        if not pd.isnull(row['answer-spec']):
            X = row['answer']
            r = False
            try:
                r = eval(row['answer-spec'])
            except:
                pass
    
            if r:
                return row['points']
            else:
                return 0.0
    
    results_files = glob('%s/*/student-answers.csv' % submissions_folder) + glob('%s/student-answers.csv' % submissions_folder)
    answer_model = json.load(open(answer_model_file))
    
    auto_score_questions = { q['id']: { 'answer-spec': q['answer-spec'], 'points': (float(q['properties']['points']) if ('points' in q['properties']) else 1.0) } for q in answer_model if 'answer-spec' in q and not ('type' in q['properties'] and q['properties']['type'] == 'open') }
    auto_score_questions = pd.DataFrame.from_dict(auto_score_questions, orient='index')

    for f in results_files:
        results_df = pd.read_csv(f, dtype={ 'student': str })
        results_df = results_df.merge(auto_score_questions, how='left', left_on='question', right_index=True)
        
        results_df['score'] = np.where(pd.isnull(results_df['answer-spec']), results_df['score'], results_df.apply(check_answer, axis=1))
        
        results_df[['student', 'question', 'score', 'answer']].to_csv(f, index=False, encoding='utf8')
        execute('touch %s/auto-scoring-done' % os.path.dirname(f))
        
    print Fore.GREEN + ('Automatically scored questions have been scored.') + Style.RESET_ALL