<div align="left">
    <h1>Modmail log viewer</h1>
    <strong><i>A simple webserver to view your selfhosted modmail logs.</i></strong>
    <br>
    <br>


<a href="https://heroku.com/deploy?template=https://github.com/kyb3r/logviewer">
    <img src="https://img.shields.io/badge/deploy_to-heroku-997FBC.svg?style=for-the-badge" />
</a>

</div>

## What is this?

In order for you to view your selfhosted logs, you have to deploy this application. Before you deploy the application, create a config var named `MONGO_URI` and put your MongoDB connection URI from the previous section into the value slot. Take the url of this app after you deploy it and input it as a config var `LOG_URL` in the modmail bot app.

## Contributing

If you can make improvements in the design and presentation of logs, please make a pull request with changes.
