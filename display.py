import os
from glob import glob
from subprocess import run
#import sys

PATH = 'D:/Uvm2018spring/CS395_Deep_Learning/final_project/tools/labelImg-master/xmls'#sys.argv[1]
# dirname = 'dd/dd'
# PATH  = 'dd'
images = [y for x in os.walk(PATH) for y in glob(os.path.join(x[0], '*.jpg'))]
for filename in images:
	print(filename)
	FULL_PATH = os.getcwd() + '/' + filename
	dirs = filename.split('/')
	parent = '/'.join(dirs[:-1])
	print(parent)
	xml_file = filename[:-3]+'xml'
	if xml_file in os.listdir(parent):
		completed = run(['python', './labelImg.py', './'+filename, './'+xml_file])

	else:
		print("\t==========NO SIGN==========")
		completed = run(['python', './labelImg.py', './'+filename])
