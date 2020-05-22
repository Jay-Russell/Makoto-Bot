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
@client.command(context=True, aliases=['Anilist'])
async def anilist(ctx, param, show):
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

	# search AniList for show and give info in return
	elif 'search' in param:

		# query of info we want from AniList
		query = '''
		query ($id: Int, $search: String, $asHtml: Boolean) {
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
	            siteUrl
	        }
		}
		'''
		
		variables = {
		    'search': show,
		    'asHtml': False
		}
			
		source = 'https://graphql.anilist.co'
		
		response = requests.post(source, json={'query': query, 'variables': variables})
		show = response.json();
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

			# limit description to three sentences
			sentences = findSentences(desc)
			if len(sentences) > 3:
				desc = desc[:sentences[2] + 1]

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
			embed.set_image(url=str(show['data']['Media']['bannerImage']))
			embed.set_thumbnail(url=str(show['data']['Media']['coverImage']['large']))
			#embed.set_author(name='Author Name', icon_url='')
			
			# if show is airing, cancelled, finished, or not released
			status = show['data']['Media']['status']

			if 'NOT_YET_RELEASED' not in status:
				embed.add_field(name='Score', value=str(show['data']['Media']['meanScore']) + '%', inline=True)
				if 'RELEASING' not in status:
					embed.add_field(name='Episodes', value=str(show['data']['Media']['episodes']), inline=True)
					
					# seperate score / episodes from season / run time 
					embed.add_field(name='.', value='.', inline=False)
					
					embed.add_field(name='Season', value=str(show['data']['Media']['seasonYear']) + ' ' + str(show['data']['Media']['season']).title(), inline=True)

					# find difference in year month and days of show's air time 
					years = abs(show['data']['Media']['endDate']['year'] - show['data']['Media']['startDate']['year'])
					months = abs(show['data']['Media']['endDate']['month'] - show['data']['Media']['startDate']['month'])
					days = abs(show['data']['Media']['endDate']['day'] - show['data']['Media']['startDate']['day'])
					
					# get rid of anything with zero
					tyme = str(days) + ' days'
					if months != 0:
						tyme += ', ' + str(months) + ' months'
					if years != 0:
						tyme += ', ' + str(years) + ' years' 
					
					embed.add_field(name='Run Time', value=tyme, inline=True)
			
			await ctx.send(embed=embed)
		else:
			await ctx.send('Response code: ' + str(response.status_code) + '\n\n' + str(show))

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
	print('\n' + mess + ' ' + str(len(mess)) + '\n')

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
	if not user.id in users:
		users[user.id] = {}
		users[user.id]['token'] = 'nothin'

# AniList connection helper method 2
async def add_token(users, user, t):
	users[user.id]['token'] = t

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