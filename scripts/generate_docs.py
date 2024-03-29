#
# Copyright (c) 2010-2011, Nick Blundell
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Nick Blundell nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
#
#
# Author: Nick Blundell <blundeln [AT] gmail [DOT] com>
# Organisation: www.nickblundell.org.uk
# 
# Description:
# 
#

import os
import sys
import re
import glob

SOURCE_DIR = os.getcwd()

try :
  from nbdebug import d
except ImportError:
  def d(*args, **kargs):pass

def run(command) :
  d(command)
  return os.system(command)


def generate_pages_from_example_code(python_file) :
  d(python_file)
  
  content = open(python_file).read()
 
  matches = []

  multiline_comment_matches = []
  for match in re.finditer("^\s\s\"\"\"(.+?)\"\"\".*?\n", content, re.DOTALL + re.MULTILINE) :
    if match:
      multiline_comment_matches.append(match)
  
  hash_comment_matches = []
  for match in re.finditer("^\s\s#(.*?)\n", content, re.DOTALL + re.MULTILINE) :
    if match:
      hash_comment_matches.append(match)

  
  test_function_matches = []
  for match in re.finditer("def\s+(.+?)_test.+?\n", content, re.DOTALL) :
    if match:
      test_function_matches.append(match)

  all_matches = []
  all_matches.extend(multiline_comment_matches)
  all_matches.extend(hash_comment_matches)
  all_matches.extend(test_function_matches)

  # Sort matches by their source positions.
  all_matches = sorted(all_matches, key=lambda x: x.start())
  
  output_blocks = []
  prev_match = None
  for match in all_matches:
    if prev_match :
      code_block = content[prev_match.end(0):match.start(0)].strip()

      if code_block :
        # Convert our assertions to showing expected outputs.
        def f(match) :
          args = match.group(1)
          if ",  " in args :
            # Since ',' may appear inside two args, we use double space to
            # indicate docs should be transformed in this way.
            return args.replace(",  ", " ---> ")
          else :
            return match.group(0)
        
        if "assert_equal" in code_block : 
          code_block = re.sub("assert_equal\((.+?)\)\s*$", f, code_block, flags=re.MULTILINE)
          # TODO: Need to handle multilines. 
          #code_block = re.sub("assert_equal\((.+?)\)\s*\n", f, code_block, flags=re.DOTALL)
          
        code_block = f"\n\n::\n\n  {code_block}\n\n"
        output_blocks.append([prev_match.end(0), code_block])
    prev_match = match


  match = None
  for match in all_matches:
    text = match.group(1)
    if match in test_function_matches:
      text = "\n\n" + " ".join([s.capitalize() for s in text.split("_")]) + "\n" + "-"*80 + "\n\n"
    elif match in multiline_comment_matches:
      text = text.replace("\n  ","\n")+"\n\n"
    elif match in hash_comment_matches:
      text = text[1:]+"\n"
    output_blocks.append((match.start(0), text))

  output_blocks = sorted(output_blocks, key=lambda x: x[0])

  output = ""
  for x in output_blocks :
    output += x[1]


  return output


def generate_docs_from_example_tests():
  examples_path = os.path.join(SOURCE_DIR, "examples")
  
  try :
    os.makedirs("docs/source/examples")
  except :
    run("rm docs/source/examples/*.rst")
  
  for source_file in glob.glob(examples_path+"/*.py") :
    name = os.path.basename(source_file).replace(".py","")
    
    # TODO: Improve handling of fully-left justified code.
    if name != "basic" :
      continue
    
    if name.startswith("_") :
      continue
    output = generate_pages_from_example_code(source_file)

    # Add page title
    output = name.capitalize() + "\n" + "="*80 + "\n\n" + output

    if output.strip() :
      open(f"docs/source/examples/{name}.rst","w").write(output)

def main():
  
  # Generate tutorials from source.
  generate_docs_from_example_tests()
  

  # Generate index.rst from our README file.
  index_content = open("README.rst").read()
  index_content = index_content.replace(".. TOC", "\n\n\n" + open("docs/source/master_toc").read())
  open("docs/source/index.rst", "w").write(index_content)
 

  exit_code = run("sphinx-build -W -b html docs/source docs/build/html")
  if exit_code :
    raise Exception("Sphinx build failed")

if __name__ == "__main__" :
  main()
