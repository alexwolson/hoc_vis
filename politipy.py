import requests
import math
import collections
import numpy as np
from scipy import spatial
from nameparser import HumanName

coalition = 'http://lda.data.parliament.uk/commonsdivisions.json?maxEx-date=2015-05-07&minEx-date=2010-05-06&exists-date=true&_view=Commons+Divisions&_page=0'
last_parl = 'http://lda.data.parliament.uk/commonsdivisions.json?maxEx-date=2017-06-08&minEx-date=2015-05-07&exists-date=true&_view=Commons+Divisions&_page=0'
this_parl = 'http://lda.data.parliament.uk/commonsdivisions.json?minEx-date=2017-06-08&exists-date=true&_view=Commons+Divisions&_page=0'
since_fifteen = 'http://lda.data.parliament.uk/commonsdivisions.json?minEx-date=2015-05-07&exists-date=true&_view=Commons+Divisions&_page=0'
votes_ever = 'http://lda.data.parliament.uk/commonsdivisions.json?_view=Commons+Divisions&_page=0'
leaders = ['Theresa May', 'Nigel Dodds', 'Jeremy Corbyn',
           'Ian Blackford', 'Tim Farron', 'Liz Roberts', 'Caroline Lucas']


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
        dtails = requests.get(
            rooturl + division['uin']).json()['result']['items'][0]['vote']
        print("Processing %d of %d: (%d votes)\t%s" %
              (i, totaldiv, len(dtails), division['title']))
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
                    mps[mpname]['party'] = vote['memberParty'].replace(" ", "")
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


def build_comparison_matrix(mps, noabsents=False):
    relations = collections.defaultdict(dict)
    for firstmp in mps.items():
        print("Generating values for %s..." % firstmp[0])
        for secondmp in mps.items():
            if noabsents:
                relations[firstmp[0]][secondmp[0]] = mp_similarity_noabsent(
                    firstmp[1], secondmp[1])
            else:
                relations[firstmp[0]][secondmp[0]] = mp_similarity(
                    firstmp[1], secondmp[1])
    return relations


def export_tsv(comparisons, filename='mpresults.tsv'):
    outfile = open(filename, 'w')
    for mpone in comparisons.keys():
        for mptwo in comparisons[mpone].keys():
            outfile.write(mpone.replace(' ', '-') + '\t' + mptwo.replace(' ',
                                                                         '-') + '\t' + str(comparisons[mpone][mptwo]) + '\n')
    outfile.close()


def create_coalition_dataset():
    divisions = load_divisions(coalition)
    mps = build_votebase(divisions)
    mtx = build_comparison_matrix(mps)
    export_tsv(mtx, 'coalition.tsv')
    return mtx


def create_last_parl_dataset():
    divisions = load_divisions(last_parl)
    mps = build_votebase(divisions)
    mtx = build_comparison_matrix(mps)
    export_tsv(mtx, 'last_parl.tsv')
    return mtx


def create_this_parl_dataset():
    divisions = load_divisions(this_parl)
    mps = build_votebase(divisions)
    mtx = build_comparison_matrix(mps)
    export_tsv(mtx, 'this_parl.tsv')
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


def bipartyplots(mtx, mps):
    partyp = collections.defaultdict(list)
    for mpone in mps.keys():
        for mptwo in mps.keys():
            if mpone != mptwo:
                if mps[mpone]['party'] != mps[mptwo]['party']:
                    partyp[mps[mpone]['party']].append(mtx[mpone][mptwo])
    return partyp


def remove_weirdlab(mps):
    for mp in mps.keys():
        if "Labour" in mps[mp]['party']:
            mps[mp]['party'] = "Labour"
        else:
            mps[mp]['party'] = mps[mp]['party'].replace(" ", "")
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


def encode_parties(mps):
    pdict = {}
    next = 0
    for mp in mps.items():
        if mp[1]['party'] not in pdict.keys():
            pdict[mp[1]['party']] = next
            next += 1
    print(pdict)
    return pdict


def plot_compass(mtx, mps):
    nmps = len(mps.keys())
    mpa = np.zeros((nmps, 3))
    colordict = encode_parties(mps)
    for i, mp in enumerate(mps.items()):
        mpa[i][0] = mtx['Jeremy Corbyn'][mp[0]]
        mpa[i][1] = mtx['Theresa May'][mp[0]]
        mpa[i][2] = colordict[mp[1]['party']]
    import scipy.io as sio
    sio.savemat("mpcompass.mat", mdict={'mpa': mpa})
    return mpa


def plot_compass_three(mtx, mps):
    nmps = len(mps.keys())
    mpa = np.zeros((nmps, 4))
    colordict = encode_parties(mps)
    for i, mp in enumerate(mps.items()):
        mpa[i][0] = mtx['Jeremy Corbyn'][mp[0]]
        mpa[i][1] = mtx['Theresa May'][mp[0]]
        mpa[i][2] = mtx['Angus Robertson'][mp[0]]
        mpa[i][3] = colordict[mp[1]['party']]
    import scipy.io as sio
    sio.savemat("mpcompass.mat", mdict={'mpa': mpa})
    return mpa


def kmeans(matx, mpv, leaders):
    originalmps = mpv
    oldleaders = []
    generation = 1
    while (oldleaders != leaders):
        print("Year %d..." % generation)
        generation += 1
        mpscores = collections.defaultdict(int)
        for mp in mpv.items():
            bestval = -1
            bestpar = ""
            for leader in leaders:
                if matx[mp[0]][leader] > bestval:
                    bestval = matx[mp[0]][leader]
                    bestpar = mpv[leader]['party']
            if bestpar != mpv[mp[0]]['party']:
                print("%s switched allegiance from %s to %s!" %
                      (mp[0], mpv[mp[0]]['party'], bestpar))
            mpv[mp[0]]['party'] = bestpar
        for mpone in mpv.items():
            for mptwo in mpv.items():
                if mpone[1]['party'] == mptwo[1]['party']:
                    mpscores[mptwo[0]] += matx[mpone[0]][mptwo[0]]
        partybestval = collections.defaultdict(int)
        partybestper = {}
        for mp in mpv.items():
            if mpscores[mp[0]] > partybestval[mp[1]['party']]:
                partybestval[mp[1]['party']] = mpscores[mp[0]]
                partybestper[mp[1]['party']] = mp[0]
        oldleaders = leaders
        leaders = []
        for ppair in partybestper.items():
            print("%s elected leader of the %s party" % (ppair[1], ppair[0]))
            leaders.append(ppair[1])
    partysize = collections.defaultdict(int)
    for mp in mpv.values():
        partysize[mp['party']] += 1
    for partypair in partysize.items():
        print("%s now has %d members" % (partypair[0], partypair[1]))
    partypie = collections.defaultdict(dict)
    for mp in mpv.items():
        oldparty = originalmps[mp[0]]['party']
        newparty = mp[1]['party']
        if oldparty not in partypie[newparty].keys():
            partypie[newparty][oldparty] = 0
        partypie[newparty][oldparty] += 1
    for party in partypie.items():
        print("%s consists of:" % party[0])
        for partytwo in party[1].items():
            print("\t%d %s" % (partytwo[1], partytwo[0]))
    print("Finished!")


def leadership_race(mps, mtx):
	candidates = [
'Michael Gove',
'Matt Hancock',
'Jeremy Hunt',
'Sajid Javid',
'Boris Johnson',
'Andrea Leadsom',
'Kit Malthouse',
'Esther McVey',
'Dominic Raab',
'Rory Stewart'
	]
	backers = {}
	backers['Michael Gove'] = '''Peter Aldous
Richard Bacon
Jack Brereton
Alberto Costa
George Eustice
George Freeman
Nick Gibb
John Hayes
Trudy Harrison
Kevin Hollinrake
Stephen Kerr
Edward Leigh
Rachel Maclean
Nicky Morgan
Bob Neill
Guy Opperman
Bob Seely
John Stevenson
Mel Stride
Tom Tugendhat
Ed Vaizey
Giles Watling'''.split('\n')

	backers['Matt Hancock'] = '''Bim Afolami
Tracey Crouch
Caroline Dinenage
Damian Green
Stephen Hammond
Caroline Spelman
Maggie Throup'''.split('\n')

	backers['Jeremy Hunt'] = '''Harriett Baldwin
Crispin Blunt
Steve Brine
James Cartlidge
Jo Churchill
Leo Docherty
Philip Dunne
Mark Field
Vicky Ford
Mike Freer
Mark Garnier
Nus Ghani
Robert Goodwill
Richard Graham
Oliver Heald
Nick Herbert
Andrew Jones
Daniel Kawczynski
John Lamont
Patrick McLoughlin
Alan Mak
David Morris
James Morris
Will Quince
John Penrose
Alec Shelbrooke
Helen Whately'''.split('\n')


	backers['Sajid Javid'] = '''Stephen Crabb
David Davies
Mims Davies
David Evenett
Kevin Foster
John Glen
Robert Halfon
Simon Hoare
Chris Philp
Chris Skidmore
Mike Wood'''.split('\n')

	backers['Boris Johnson'] = '''Nigel Adams
Stuart Andrew
Jake Berry
Peter Bone
Andrew Bridgen
Conor Burns
Simon Clarke
Nadine Dorries
Nigel Evans
Zac Goldsmith
Jo Johnson
David Jones
Mark Menzies
Johnny Mercer
Amanda Milling
Sheryll Murray
Mike Penning
Jacob Rees-Mogg
Andrew Rosindell
Ross Thomson
Anne-Marie Trevelyan
Matt Warman
John Whittingdale
Gavin Williamson'''.split('\n')

	backers['Andrea Leadsom'] = '''Chris Heaton-Harris
Tim Loughton
Heather Wheeler'''.split('\n')

	backers['Kit Malthouse'] = '''Alex Burghart
Sarah Newton'''.split('\n')

	backers['Esther McVey'] = '''Ben Bradley
Philip Davies
Pauline Latham
Andrew Lewer
Gary Streeter'''.split('\n')

	backers['Dominic Raab'] = '''Henry Bellingham
Suella Braverman
Maria Caulfield
Rehman Chishti
Robert Courts
David Davis
Helen Grant
Chris Green
Eddie Hughes
Andrea Jenkyns
Gareth Johnson
Maria Miller
Anne-Marie Morris
Andrew Murrison
Tom Pursglove
Hugo Swire
Robert Syms
Michael Tomlinson
Shailesh Vara
Nadhim Zahawi'''.split('\n')

	backers['Rory Stewart'] = '''Victoria Prentis
Nicholas Soames'''.split('\n')

	tories = []
	for k,v in mps.items():
		if v['party'] == 'Conservative':
			tories.append(k)

	voters = [t for t in tories if t not in candidates]

	for v in backers.values():
		for vi in v:
			if vi in voters:
				voters.remove(vi)

	for k,v in backers.items():
		for vi in v:
			if vi not in tories:
				backers[k].remove(vi)

	for k in voters:
		if k not in tories:
			voters.remove(k)
	c = []
	from copy import deepcopy
	from tqdm import tqdm
	for i in tqdm(range(1000)):
		c.append(
			dothevoting(
				mtx,
				tories,
				deepcopy(voters),
				deepcopy(candidates),
				deepcopy(backers))
		)
	print(collections.Counter(c))
	

def dothevoting(mtx,tories,voters,candidates,backers):
	while(len(candidates) > 1):
		votes = {}

		for candidate in candidates:
			votes[candidate] = 1 + len(backers[candidate])

		for voter in voters:
			options = collections.defaultdict(float)
			for candidate in candidates:
				if mtx[voter][candidate] > 0:
					options[candidate] += mtx[voter][candidate]
				for backer in backers[candidate]:
					if mtx[voter][backer] > 0:
						options[candidate] += mtx[voter][backer]
			weights = np.asarray(list(options.values()))
			weights /= np.sum(weights)
			votes[
				np.random.choice(list(options.keys()),p=weights)
			] += 1

		worstmp = ''
		minval = 330
		for k,v in votes.items():
			if v <= minval:
				worstmp = k
				minval = v

		candidates.remove(worstmp)
		voters.append(worstmp)
		for mp in backers[worstmp]:
			voters.append(mp)
		backers.pop(worstmp)
	return(candidates[0])
