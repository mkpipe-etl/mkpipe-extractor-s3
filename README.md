# MkPipe

**MkPipe** is a modular, open-source ETL (Extract, Transform, Load) tool that allows you to integrate various data sources and sinks easily. It is designed to be extensible with a plugin-based architecture that supports extractors, transformers, and loaders.  

## Documentation

For more detailed documentation, please visit the [GitHub repository](https://github.com/mkpipe-etl/mkpipe).

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.


## mkpipe_project.yaml Variables
```yaml
...
  connections:
    source:
      bucket_name: xxx 
      s3_prefix: xxx # optional
      aws_access_key: "xxx"
      aws_secret_key: "xxx"
...
```

