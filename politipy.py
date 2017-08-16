import requests, math, collections
import numpy as np
from scipy import spatial
from nameparser import HumanName

last_parl = 'http://lda.data.parliament.uk/commonsdivisions.json?maxEx-date=2017-06-08&minEx-date=2015-05-07&exists-date=true&_view=Commons+Divisions&_page=0'
since_fifteen = 'http://lda.data.parliament.uk/commonsdivisions.json?minEx-date=2015-05-07&exists-date=true&_view=Commons+Divisions&_page=0'
votes_ever = 'http://lda.data.parliament.uk/commonsdivisions.json?_view=Commons+Divisions&_page=0'

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
	
def strip_name(name):
	stripped_name = HumanName(name)
	return stripped_name.first + ' ' + stripped_name.last
	
def build_votebase(divisions):
	mps = {}
	rooturl = 'http://lda.data.parliament.uk/commonsdivisions.json?uin='
	totaldiv = len(divisions)
	for i, division in enumerate(divisions):
		dtails = requests.get(rooturl + division['uin']).json()['result']['items'][0]['vote']
		print("Processing %d of %d: (%d votes)\t%s" % (i,totaldiv, len(dtails), division['title']))
		for vote in dtails:
			try:
				mpname = strip_name(vote['memberPrinted']['_value'])
			except:
				pass
			if vote['type'] == "http://data.parliament.uk/schema/parl#NoVote":
				mpaye = -1
			elif vote['type'] == "http://data.parliament.uk/schema/parl#AyeVote":
				mpaye = 1
			else:
				mpaye = 0
			if mpname not in mps.keys():
				mps[mpname] = {}
				mps[mpname]['votes'] = {}
				mps[mpname]['party'] = vote['memberParty']
			mps[mpname]['votes'][division['uin']] = mpaye
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
	
def mp_similarity_noabsent(mpone, mptwo):
	if (mpone == mptwo):
		return 1
	votesone = mpone['votes']
	votestwo = mptwo['votes']
	votesincommon = votesone.keys() & votestwo.keys()
	if (len(votesincommon) == 0):
		return 0
	vecone = np.zeros(len(votesincommon))
	vectwo = np.zeros(len(votesincommon))
	nextloc = 0
	for vote in votesincommon:
		vecone[nextloc] = votesone[vote]
		vectwo[nextloc] = votestwo[vote]
		nextloc += 1
	return 1 - spatial.distance.cosine(vecone, vectwo)

def build_comparison_matrix(mps, noabsents = False):
	relations = collections.defaultdict(dict)
	for firstmp in mps.items():
		print("Generating values for %s..." % firstmp[0])
		for secondmp in mps.items():
			if noabsents:
				relations[firstmp[0]][secondmp[0]] = mp_similarity_noabsent(firstmp[1], secondmp[1])
			else:
				relations[firstmp[0]][secondmp[0]] = mp_similarity(firstmp[1], secondmp[1])
	return relations
	
def export_tsv(comparisons, filename='mpresults.tsv'):
	outfile = open(filename,'w')
	for mpone in comparisons.keys():
		for mptwo in comparisons[mpone].keys():
			outfile.write(mpone.replace(' ','-') + '\t' + mptwo.replace(' ','-') + '\t' + str(comparisons[mpone][mptwo] + 1) + '\n')
	outfile.close()
	
def create_last_parl_dataset():
	divisions = load_divisions(last_parl)
	mps = build_votebase(divisions)
	mtx = build_comparison_matrix(mps)
	export_tsv(mtx, 'last_parl.tsv')
	return mtx
	
def create_since_fifteen_dataset():
	divisions = load_divisions(since_fifteen)
	mps = build_votebase(divisions)
	mtx = build_comparison_matrix(mps, True)
	export_tsv(mtx, 'since_fifteen.tsv')
	return mtx
	
def create_full_dataset():
	divisions = load_divisions(votes_ever)
	mps = build_votebase(divisions)
	mtx = build_comparison_matrix(mps, True)
	export_tsv(mtx, 'votes_ever.tsv')
	return mtx
	
def partyplots(mtx, mps):
	partyp = collections.defaultdict(list)
	for mpone in mps.keys():
		for mptwo in mps.keys():
			if mpone != mptwo:
				if mps[mpone]['party'] == mps[mptwo]['party']:
					partyp[mps[mpone]['party']].append(mtx[mpone][mptwo])
	return partyp