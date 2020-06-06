import random
import json
import graphene
import os
from os import path
import requests
import time
import discord
from discord.ext import commands, tasks

# setup bot instance
client = commands.Bot(command_prefix = '?')

# (local) project directory
location = 'C:\\Users\\Jay\\Desktop\\code\\makoto-bot'
os.chdir(location)

# token ID
token = None

if path.exists('token.txt'): 
	token = str(open('token.txt', 'r').read())

# AniList authentication URL parameters
redirect_uri = 'https://anilist.co/api/v2/oauth/pin'
secret = None
ani_id = None

if path.exists('ani_id.txt') and path.exists('ani_secret.txt'):
	ani_id = str(open('ani_id.txt', 'r').read())
	secret = str(open('ani_secret.txt', 'r').read())

# create AniList authentication URL
authLink = 'https://anilist.co/api/v2/oauth/authorize?client_id=' + ani_id + '&redirect_uri=' + redirect_uri + '&response_type=code'

# vars for checking if bot should check for response to AniList verification
user = None
monitor = False
authCode = None

@client.event
async def on_ready():
	game = discord.Game('with a harem')
	await client.change_presence(status=discord.Status.online, activity=game)
	print('Online')

# lists anilist commands
@client.command(context=True)
async def a(ctx, param):
	print('\n' + param + '\n')
	if 'help' in param:
		await ctx.send('```help: list commands\nconnect: link account to discord```')
	# link discord and anilist account
	elif 'connect' in param:
		await ctx.send('Connect account by logging in to AniList with the following link and DMing Makoto BOT the authentication code\n**DO NOT PUBLICLY POST IT**\nYou have 30 seconds\nClick here to get your Authorization Code: ' + authLink)
		
		# Start checking for verfication code
		global user
		global monitor

		user = ctx.author
		monitor = True

	# attach Anilist user to discord account
	elif 'register' == param or 'r' == param:
		name = str(ctx.message.content)[(len(ctx.prefix) + len('a ' + param + ' ')):]
		query = '''
			query($id: Int, $search: String) {
				User (id: $id, search: $search) {
					id
					name
				}
			}
		'''

		variables = {
			'search' : name
		}

		url = 'https://graphql.anilist.co'

		response = requests.post(url, json={'query': query, 'variables': variables})
		rScore = response.json()

		# first check if user in already registered
		with open('users.json', 'r') as f:
			users = json.load(f)

		# pair user and token through helper methods
		if str(ctx.message.author.id) in users:
			print(ctx.message.author.id)
			await ctx.send('you are already registered')
		else:
			await update_data(users, ctx.message.author)
			await add_id_name(users, ctx.message.author, rScore['data']['User']['id'], rScore['data']['User']['name'])
			await ctx.send('registered!')
		
		# write to file
		with open('users.json', 'w') as f:
			json.dump(users, f)
		
	# search AniList for show and give info in return
	elif 'search' == param or 's' == param :
		show = str(ctx.message.content)[(len(ctx.prefix) + len('a ' + param + ' ')):]
		print(show)
		# query of info we want from AniList
		query = '''
		query ($id: Int, $search: String, $asHtml: Boolean, $isMain: Boolean) {
	        Media (id: $id, search: $search) {
	            id
	            title {
	                romaji
	            }
	            status
	            description(asHtml: $asHtml)
	            startDate {
	            	year
	            	month
	            	day
	            }
	            endDate {
	            	year
	            	month
	            	day
	            }
	            season
	            seasonYear
	            episodes
	            coverImage {
	            	extraLarge
	            	large
	            	medium
	            	color
	            }
	            bannerImage
	            genres
	            meanScore
	            popularity
	            studios (isMain: $isMain) {
	            	nodes {
	            		name
	            		siteUrl
	            	}
	            }
	            siteUrl
	        }
		}
		'''
		
		variables = {
		    'search': show,
		    'asHtml': False,
		    'isMain': True
		}
			
		source = 'https://graphql.anilist.co'
		
		response = requests.post(source, json={'query': query, 'variables': variables})
		show = response.json()
		if response.status_code == 200:
			# parse out website styling
			desc = str(show['data']['Media']['description'])

			# italic
			desc = desc.replace('<i>', '*')
			desc = desc.replace('</i>', '*')
			# bold
			desc = desc.replace('<b>', '**')
			desc = desc.replace('</b>', '**')
			# remove br
			desc = desc.replace('<br>', '')

			# keep '...' in
			desc = desc.replace('...', '><.')

			# limit description to three sentences
			sentences = findSentences(desc)
			if len(sentences) > 3:
				desc = desc[:sentences[2] + 1]

			# re-insert '...'
			desc = desc.replace('><', '..')

			# make genre list look nice
			gees = str(show['data']['Media']['genres'])
			gees = gees.replace('\'', '')
			gees = gees.replace('[', '')
			gees = gees.replace(']', '')

			embed = discord.Embed(
				title = str(show['data']['Media']['title']['romaji']),
				description = desc,
				color = discord.Color.blue(),
				url = str(show['data']['Media']['siteUrl'])
			)

			embed.set_footer(text=gees)
			print(str(show['data']['Media']['coverImage']['large']))
			if str(show['data']['Media']['bannerImage']) != 'None':
				embed.set_image(url=str(show['data']['Media']['bannerImage']))

			if str(show['data']['Media']['coverImage']['large']) != 'None':
				embed.set_thumbnail(url=str(show['data']['Media']['coverImage']['large']))

			try:
				embed.set_author(name=str(show['data']['Media']['studios']['nodes'][0]['name']), url=str(show['data']['Media']['studios']['nodes'][0]['siteUrl']))
			except IndexError:
				print('empty studio name or URL')

			# if show is airing, cancelled, finished, or not released
			status = show['data']['Media']['status']

			if 'NOT_YET_RELEASED' not in status:
				embed.add_field(name='Score', value=str(show['data']['Media']['meanScore']) + '%', inline=True)
				embed.add_field(name='Popularity', value=str(show['data']['Media']['popularity']) + ' users', inline=True)
				if 'RELEASING' not in status:
					embed.add_field(name='Episodes', value=str(show['data']['Media']['episodes']), inline=False)
					
					embed.add_field(name='Season', value=str(show['data']['Media']['seasonYear']) + ' ' + str(show['data']['Media']['season']).title(), inline=True)

					# find difference in year month and days of show's air time 
					try:
						air = True
						years = abs(show['data']['Media']['endDate']['year'] - show['data']['Media']['startDate']['year'])
						months = abs(show['data']['Media']['endDate']['month'] - show['data']['Media']['startDate']['month'])
						days = abs(show['data']['Media']['endDate']['day'] - show['data']['Media']['startDate']['day'])
					except TypeError:
						print('Error calculating air time')
						air = False

					# get rid of anything with zero
					if air:
						tyme = str(days) + ' days'
						if months != 0:
							tyme += ', ' + str(months) + ' months'
						if years != 0:
							tyme += ', ' + str(years) + ' years' 
						
						embed.add_field(name='Run Time', value=tyme, inline=True)
			
			await ctx.send(embed=embed)
		else:
			await ctx.send('Response code: ' + str(response.status_code) + '\n\n' + str(show))

	elif 'c' == param or 'character' == param:
		print('\nin character\n')
		character = str(ctx.message.content)[(len(ctx.prefix) + len('a ' + param + ' ')):]

		query = '''
			query ($id: Int, $search: String) {
				Character (id: $id, search: $search) {
					id
					name {
						full
						alternative
					}
					image {
						large
					}
					media {
						nodes {
							title {
								romaji
							}
							coverImage {
								medium
							}
							siteUrl
						}
					}
					siteUrl
				}
			}
		'''

		variables = {
			'search': character
		}

		url = 'https://graphql.anilist.co'
		
		response = requests.post(url, json={'query': query, 'variables': variables})
		character = response.json()

		embed = discord.Embed(
				title = str(character['data']['Character']['name']['full']),
				color = discord.Color.blue(),
				url = str(character['data']['Character']['siteUrl'])
			)

		alts = str(character['data']['Character']['name']['alternative'])
		alts = alts.replace('\'', '')
		alts = alts.replace('[', '')
		alts = alts.replace(']', '')

		embed.set_image(url=str(character['data']['Character']['image']['large']))
		embed.set_author(name=str(character['data']['Character']['media']['nodes'][0]['title']['romaji']), url=str(character['data']['Character']['media']['nodes'][0]['siteUrl']), icon_url=str(character['data']['Character']['media']['nodes'][0]['coverImage']['medium']))
		embed.set_footer(text=alts)

		await ctx.send(embed=embed)



def findSentences(s):
	return [i for i, letter in enumerate(s) if letter == '.' or letter == '?' or letter == '!']	

# Resetting variables for security
@tasks.loop(seconds=30)
async def change_vars():
	global monitor
	global user
	monitor = None
	user = None

# Check user messages
@client.event
async def on_message(message):
	# allow access to monitor variable
	global monitor

	mess = message.content

	# checking Authentication Code
	if mess.startswith('def') and len(mess) == 736 and message.author is user and monitor:
		global authCode

		authCode = mess

		await message.channel.send('Authentication Code recieved!')
		print('About to check authCode')

		if authCode is not None and len(authCode) == 736:
			data = {
		    'grant_type': 'authorization_code',
		    'client_id': ani_id,
		    'client_secret': secret,
		    'redirect_uri': redirect_uri, 
		    'code': authCode
		  	}

			# send POST request to AniList
			r = requests.post('https://anilist.co/api/v2/oauth/token', data)
			if r.status_code == 200:
				await message.channel.send('successfully connected!')
				json_data = r.json()
				print(json_data)
				print('\n' + json_data['access_token'] + '\n')

				# first check if user in already registered
				with open('users.json', 'r') as f:
					users = json.load(f)

				# pair user and token through helper methods
				await update_data(users, message.author)
				await add_token(users, message.author, json_data['access_token'])

				# write to file
				with open('users.json', 'w') as f:
					json.dump(users, f)

			else:
				await message.channel.send('an error occurred: ' + str(r.status_code))

			# clear authentication code and monitoring
			authCode = None
			monitor = False
		else:
			await message.channel.send('verification failed')

	if 'vibe' in mess:
		await message.channel.send('check')
	# allow commands to function
	await client.process_commands(message)

# AniList account connection helper method 1
async def update_data(users, user):
	if user.id not in users:
		users[user.id] = {}
		users[user.id]['token'] = 'nothin'

# AniList connection helper method 2
async def add_token(users, user, t):
	users[user.id]['token'] = t

#
async def add_id_name(users, user, id, name):
	users[user.id]['id'] = id
	users[user.id]['name'] = name

# laying down the facts (Inside jokes, don't take these seriously)
@client.command(aliases=['facts'])
async def fact(ctx):
	responses = ['Klima is a cuck',
				'Overwatch is shit',
				'osu! is the greatest game of all time',
				'Epstein was murdered by the Clintons',
				'Xbox is a dead console',
				'Mara is a demon',
				'Prison School is 10/10',
				'2D > 3D',
				'FMAB is the bestest anime',
				'Although African Americans take up 14 percent of the population, they commit 40 percent of all crimes',
				'Best Joe Rogan episode was the one with Alex Jones and Mr. Bravo',
				'Makoto cares about your education']
	await ctx.send(random.choice(responses))

client.run(token)