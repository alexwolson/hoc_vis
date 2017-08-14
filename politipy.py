import requests, math
import numpy as np
from scipy import spatial
import collections

first_url = 'http://lda.data.parliament.uk/commonsdivisions.json?maxEx-date=2017-06-08&minEx-date=2015-05-07&exists-date=true&_view=Commons+Divisions&_page=0'

def load_divisions(nexturl):
	divisions = []
	firstresult = requests.get(nexturl).json()['result']
	nexturl = firstresult['next']
	for division in firstresult['items']:
		print("Division: %s" % division['title'])
		divisions.append(division)
	dkeys = firstresult.keys()
	divisionsRemain = True
	while divisionsRemain:
		divr = requests.get(nexturl).json()['result']
		dkeys = divr.keys()
		if 'next' in dkeys:
			nexturl = divr['next']
		else:
			divisionsRemain = False
		for division in divr['items']:
			print("Division: %s" % division['title'])
			divisions.append(division)
	print("Retrieved %d divisions" % len(divisions))
	return divisions
	
def build_votebase(divisions):
	mps = {}
	rooturl = 'http://lda.data.parliament.uk/commonsdivisions.json?uin='
	for division in divisions:
		dtails = requests.get(rooturl + division['uin']).json()['result']['items'][0]['vote']
		print("Processing division: (%d votes)\t%s" % (len(dtails), division['title']))
		for vote in dtails:
			mpname = vote['memberPrinted']['_value']
			mpaye = vote['type'] == "http://data.parliament.uk/schema/parl#AyeVote"
			if mpname not in mps.keys():
				mps[mpname] = {}
				mps[mpname]['votes'] = {}
				mps[mpname]['party'] = vote['memberParty']
			mpval = -1
			if mpaye:
				mpval = 1
			mps[mpname]['votes'][division['uin']] = mpval
	return mps	

def mp_similarity(mpone, mptwo):
	if (mpone == mptwo):
		return 1
	votesone = mpone['votes']
	votestwo = mptwo['votes']
	votesincommon = votesone.keys() | votestwo.keys()
	vecone = np.zeros(len(votesincommon))
	vectwo = np.zeros(len(votesincommon))
	nextloc = 0
	for vote in votesincommon:
		if vote in votesone.keys():
			vecone[nextloc] = votesone[vote]
		if vote in votestwo.keys():
			vectwo[nextloc] = votestwo[vote]
		nextloc += 1
	return 1 - spatial.distance.cosine(vecone, vectwo)
	
def build_comparison_matrix(mps):
	relations = collections.defaultdict(dict)
	for firstmp in mps.items():
		print("Generating values for %s..." % firstmp[0])
		for secondmp in mps.items():
			relations[firstmp[0]][secondmp[0]] = mp_similarity(firstmp[1], secondmp[1])
	return relations
	
def export_tsv(comparisons):
	outfile = open('mpresults.tsv','w')
	for mpone in comparisons.keys():
		for mptwo in comparisons[mpone].keys():
			outfile.write(mpone.replace(' ','-') + '\t' + mptwo.replace(' ','-') + '\t' + str(comparisons[mpone][mptwo] + 1) + '\n')
	outfile.close()