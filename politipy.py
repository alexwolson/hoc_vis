import requests, math, collections
import numpy as np
from scipy import spatial
from nameparser import HumanName

last_parl = 'http://lda.data.parliament.uk/commonsdivisions.json?maxEx-date=2017-06-08&minEx-date=2015-05-07&exists-date=true&_view=Commons+Divisions&_page=0'
this_parl = 'http://lda.data.parliament.uk/commonsdivisions.json?minEx-date=2017-06-08&exists-date=true&_view=Commons+Divisions&_page=0'
since_fifteen = 'http://lda.data.parliament.uk/commonsdivisions.json?minEx-date=2015-05-07&exists-date=true&_view=Commons+Divisions&_page=0'
votes_ever = 'http://lda.data.parliament.uk/commonsdivisions.json?_view=Commons+Divisions&_page=0'
leaders = ['Theresa May', 'Nigel Dodds', 'Jeremy Corbyn', 'Ian Blackford', 'Tim Farron', 'Liz Roberts', 'Caroline Lucas']

def load_divisions(nexturl):
	divisions = []
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
				if "Labour" in vote['memberParty']:
					mps[mpname]['party'] = "Labour"
				else:
					mps[mpname]['party'] = vote['memberParty'].replace(" ","")
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
	
def load_data(votes):
	divisions = load_divisions(votes)
	mps = build_votebase(divisions)
	mtx = build_comparison_matrix(mps, True)
	return (mps, mtx)
	
def partyplots(mtx, mps):
	partyp = collections.defaultdict(list)
	for mpone in mps.keys():
		for mptwo in mps.keys():
			if mpone != mptwo:
				if mps[mpone]['party'] == mps[mptwo]['party']:
					partyp[mps[mpone]['party']].append(mtx[mpone][mptwo])
	return partyp

def remove_weirdlab(mps):
	for mp in mps.keys():
		if "Labour" in mps[mp]['party']:
			mps[mp]['party'] = "Labour"
		else:
			mps[mp]['party'] = mps[mp]['party'].replace(" ","")
	return mps
	
def find_traitors(mtx, mps, leaders):
	traitors = []
	for mp in mps.items():
		max_match = -1
		best_party = ""
		for leader in leaders:
			if mtx[mp[0]][leader] > max_match:
				max_match = mtx[mp[0]][leader]
				best_party = mps[leader]['party']
		if mp[1]['party'] != best_party:
			traitors.append((mp[0], mp[1]['party'], best_party))
	return traitors
	
def kmeans(mtx, mps, leaders):
	oldleaders = []
	generation = 1
	while (oldleaders != leaders):
		print("Year %d..." % generation)
		generation += 1
		mpscores = collections.defaultdict(int)
		for mp in mps.items():
			bestval = -1
			bestpar = ""
			for leader in leaders:
				if mtx[mp[0]][leader] > bestval:
					bestval = mtx[mp[0]][leader]
					bestpar = mps[leader]['party']
			if bestpar != mps[mp[0]]['party']:
				print("%s switched allegiance from %s to %s!" % (mp[0], mps[mp[0]]['party'], bestpar))
			mps[mp[0]]['party'] = bestpar
		for mpone in mps.items():
			for mptwo in mps.items():
				if mpone[1]['party'] == mptwo[1]['party']:
					mpscores[mptwo[0]] += mtx[mpone[0]][mptwo[0]]
		partybestval = collections.defaultdict(int)
		partybestper = {}
		for mp in mps.items():
			if mpscores[mp[0]] > partybestval[mp[1]['party']]:
				partybestval[mp[1]['party']] = mpscores[mp[0]]
				partybestper[mp[1]['party']] = mp[0]
		oldleaders = leaders
		leaders = []
		for ppair in partybestper.items():
			print("%s elected leader of the %s party" % (ppair[1], ppair[0]))
			leaders.append(ppair[1])
	partysize = collections.defaultdict(int)
	for mp in mps.values():
		partysize[mp['party']] += 1
	for partypair in partysize.items():
		print("%s now has %d members" % (partypair[0], partypair[1]))
	print("Finished!")