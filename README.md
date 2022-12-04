# TLE

TLE is a Discord bot centered around Competitive Programming.

Join our [TLE Community Server](https://discord.gg/eYNJsDhwdN) to use the bot and get the latest updates!

**NOTE:** This is a fork of the [original TLE](https://github.com/cheran-senthil/TLE) by [cheran-senthil](https://github.com/cheran-senthil).

## Main features

✔️ Support slash commands.

✔️ Recommend problems (can be given rating and tags).

✔️ Recommend / create mashup contest.

✔️ Compete coding with other people.

✔️ Generate leaderboards (weekly, gitgudders, ...).

✔️ Generate contest ranklist (with rating change predictor).

✔️ Plot various graphs (rating, performance, speed, ...).

✔️ List solved problems (with filter or comparator).

✔️ Setup contests reminder.

✔️ Update members' role after finished contests.

✔️ Automatically create codeforces/codechef roles.


TLE is a Discord bot centered around Competitive Programming.

# Hosting Guide
## Creating A Discord Bot
1. Follow this [guide](https://www.freecodecamp.org/news/create-a-discord-bot-with-javascript-nodejs/) to create a new discord bot account and invite that to your server.
2. To keep things simple and easy give it Admin Perms and Move the Role to top.

## Creating A Firebase Storage Bucket for Database Backups
1. Navigate to [Firebase Web Console](https://console.firebase.google.com/)
2. Create a Project and Naviage to project settings. URL looks like https://console.firebase.google.com/u/0/project/test-12874/settings/serviceaccounts/adminsdk.

3. Click on "Create Service Account" and then "Generate new private key". Save the JSON File safely.

4. Navigate to Build -> Storage -> Get Started. And create a Bucket. Save the Bucket URL (ProjectName.appspot.com).

## Creating [CLIST API](https://clist.by/) Key
- Navigate to [Clist API Docs](https://clist.by/api/v2/doc/) and click on "show my api-key". And Save the Param Query. Ex. username=iwant&api_key=e4c97d624a7b963322ef90e651a5d21f000ac509

## Creating A Heroku App
1. Fork [Repo](https://github.com/Better-CF/TLE)
2. Change heroku stack to container [link](https://stackoverflow.com/questions/59725708/set-the-stack-for-an-existing-heroku-app-from-heroku-18-to-container-for-a-doc)
3. Connect Github with Heroku and Deploy app
4. Head Over to Settings and Fill in the following Variables
5. Paste your discord bot token in "BOT_TOKEN"
6. Paste your clist api param query (username=iwant&api_key=e4c97d624a7b963322ef90e651a5d21f000ac509) in "CLIST_API_TOKEN" 
7. Encode the contents of Firebase JSON file in [base64](https://www.base64encode.org/) and Paste encoded string in "FIREBASE_ADMIN_JSON"
8. Paste ID of a Discord Channel where you will want the bot to log in "LOGGING_COG_CHANNEL_ID"
9. Paste in Storage Bucket URL in "STORAGE_BUCKET"
10. Set "ALLOW_DUEL_SELF_REGISTER" to true/false
11. Set "TLE_MODERATOR" to Moderator or any Role Name
12. Navigate to Resources and turn on the Dyno